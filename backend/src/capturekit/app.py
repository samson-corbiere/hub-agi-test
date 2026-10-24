"""The CaptureKit ingest API (docs/api-contract.md)."""

import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import cast, create_engine, insert, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from capturekit import config
from capturekit.meta import InvalidMeta, describe_location, validate_meta
from capturekit.models import CaptureSession, FileStatus, SessionFile
from capturekit.schemas import SessionOut


def create_app(database_url: str | None = None) -> FastAPI:
    engine = create_engine(database_url or config.database_url())
    make_db_session = sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(title="CaptureKit ingest API", lifespan=lifespan)

    # The contract's error shape is {"detail": "<human-readable reason>"}, also for 422.
    @app.exception_handler(RequestValidationError)
    async def request_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        reasons = "; ".join(
            f"{describe_location(error['loc'])}: {error['msg']}" for error in exc.errors()
        )
        return JSONResponse(
            {"detail": f"Invalid request: {reasons}"},
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    @app.exception_handler(InvalidMeta)
    async def invalid_meta(_: Request, exc: InvalidMeta) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    # Anything unexpected: still the contract's JSON shape. The exception is re-raised
    # after this response is sent, so the server still logs the traceback.
    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            {"detail": "Internal server error"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    def get_db() -> Iterator[Session]:
        with make_db_session() as db:
            yield db

    Db = Annotated[Session, Depends(get_db)]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/sessions",
        status_code=status.HTTP_201_CREATED,
        responses={
            200: {"description": "Already registered with this exact metadata"},
            409: {"description": "Already registered with different metadata"},
            422: {"description": "Body is not a valid meta.json"},
        },
    )
    def register_session(body: Annotated[Any, Body()], db: Db, response: Response) -> SessionOut:
        meta = validate_meta(body)
        session_id = uuid.UUID(meta["session_id"])

        # ON CONFLICT makes concurrent replays safe: only one request inserts, the
        # others wait for it and then see the committed row.
        inserted = db.execute(
            pg_insert(CaptureSession)
            .values(
                id=session_id,
                platform=meta["platform"],
                device_model=meta["device_model"],
                os_version=meta["os_version"],
                meta=meta,
            )
            .on_conflict_do_nothing(index_elements=[CaptureSession.id])
            .returning(CaptureSession.id)
        ).scalar_one_or_none()

        if inserted is None:
            # Compare jsonb to jsonb in Postgres: both sides get the same number
            # normalisation, so the comparison is exact for anything jsonb can store.
            identical = db.scalar(
                select(CaptureSession.meta == cast(meta, JSONB)).where(
                    CaptureSession.id == session_id
                )
            )
            if not identical:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Session {session_id} is already registered with different metadata.",
                )
            response.status_code = status.HTTP_200_OK
        else:
            db.execute(
                insert(SessionFile),
                [
                    {
                        "session_id": session_id,
                        "name": f["name"],
                        "size": f["size"],
                        "sha256": f["sha256"],
                        "status": FileStatus.EXPECTED,
                    }
                    for f in meta["files"]
                ],
            )
            db.commit()

        session = db.get_one(CaptureSession, session_id)
        return SessionOut.from_model(session)

    return app
