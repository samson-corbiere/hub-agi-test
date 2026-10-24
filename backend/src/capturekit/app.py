"""The CaptureKit ingest API (docs/api-contract.md)."""

import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import cast, create_engine, func, insert, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from capturekit import config
from capturekit.meta import InvalidMeta, describe_location, validate_meta
from capturekit.models import CaptureSession, FileStatus, SessionFile
from capturekit.schemas import FileOut, SessionOut
from capturekit.uploads import (
    MAX_FILE_SIZE,
    SHA256_HEX,
    UPLOADED_FILE_NAMES,
    BodyTooLarge,
    Upload,
    receive_upload,
)


def create_app(
    database_url: str | None = None,
    data_dir: Path | None = None,
    max_file_size: int = MAX_FILE_SIZE,
) -> FastAPI:
    """The API. data_dir defaults to DATA_DIR; max_file_size is lowered by tests."""
    engine = create_engine(database_url or config.database_url())
    data_dir = data_dir or config.data_dir()
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

    def store_upload(
        session_id: uuid.UUID, name: str, header_sha256: str, upload: Upload
    ) -> tuple[FileOut, bool]:
        """Record the upload and move it into place. Returns (file, newly received)."""
        with make_db_session() as db:
            file = db.get_one(SessionFile, (session_id, name))
            if file.status == FileStatus.RECEIVED:
                if upload.sha256 != file.sha256:
                    raise HTTPException(
                        status.HTTP_409_CONFLICT,
                        f"{name} was already received with SHA-256 {file.sha256}; "
                        f"this upload's SHA-256 is {upload.sha256}.",
                    )
                return FileOut.from_model(file), False
            if upload.sha256 != header_sha256 or upload.sha256 != file.sha256:
                file.status = FileStatus.CORRUPT
                db.commit()
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    f"{name} is corrupt: received SHA-256 {upload.sha256}, but the "
                    f"X-Content-SHA256 header says {header_sha256} and meta.json "
                    f"declares {file.sha256}.",
                )
            upload.move_to(data_dir / "sessions" / str(session_id) / name)
            file.status = FileStatus.RECEIVED
            file.size = upload.size
            file.received_at = func.now()
            db.commit()
            db.refresh(file)
            return FileOut.from_model(file), True

    def session_exists(session_id: uuid.UUID) -> bool:
        with make_db_session() as db:
            return db.get(CaptureSession, session_id) is not None

    @app.put(
        "/sessions/{session_id}/files/{name}",
        status_code=status.HTTP_201_CREATED,
        responses={
            200: {"description": "Already received with this exact content; not rewritten"},
            400: {"description": "Not a session file name, or bad X-Content-SHA256"},
            404: {"description": "Unknown session"},
            409: {"description": "Already received with different content"},
            413: {"description": "Body larger than the limit"},
            422: {"description": "Body doesn't match X-Content-SHA256 or meta.json"},
        },
    )
    async def upload_file(
        session_id: str, name: str, request: Request, response: Response
    ) -> FileOut:
        # Parsed by hand: a path that isn't a UUID names no session (404, not 422).
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            sid = None
        if sid is None or not await run_in_threadpool(session_exists, sid):
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Session {session_id} not found.")
        if name not in UPLOADED_FILE_NAMES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{name!r} is not a session file; expected one of "
                f"{', '.join(sorted(UPLOADED_FILE_NAMES))}.",
            )
        header_sha256 = request.headers.get("X-Content-SHA256")
        if header_sha256 is None or not SHA256_HEX.fullmatch(header_sha256):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "X-Content-SHA256 must be the body's SHA-256 as 64 lowercase hex characters.",
            )
        # Closing the connection stops the client from sending the rest of the body
        # (otherwise the server keeps reading it to reach the next request).
        too_large = HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"{name} is larger than the {max_file_size}-byte limit.",
            headers={"Connection": "close"},
        )
        content_length = request.headers.get("Content-Length")
        if content_length is not None:
            if not content_length.isdigit():
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Content-Length.")
            if int(content_length) > max_file_size:
                raise too_large

        try:
            upload = await receive_upload(
                request, data_dir / "sessions" / str(sid), name, max_file_size
            )
        except BodyTooLarge:
            raise too_large from None
        try:
            file, created = await run_in_threadpool(store_upload, sid, name, header_sha256, upload)
        finally:
            upload.discard()
        if not created:
            response.status_code = status.HTTP_200_OK
        return file

    return app
