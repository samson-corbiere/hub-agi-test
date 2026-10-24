"""The CaptureKit ingest API."""

import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, HTTPException, Response, status
from sqlalchemy import create_engine, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from capturekit import config
from capturekit.models import Session, SessionFile
from capturekit.schemas import SessionOut


def create_app(database_url: str | None = None) -> FastAPI:
    engine = create_engine(database_url or config.database_url())
    make_db_session = sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(title="CaptureKit ingest API", lifespan=lifespan)

    def get_db() -> Iterator[DbSession]:
        with make_db_session() as db:
            yield db

    Db = Annotated[DbSession, Depends(get_db)]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/sessions",
        status_code=status.HTTP_201_CREATED,
        responses={200: {"description": "Already registered with this exact metadata"}},
    )
    def register_session(
        meta: Annotated[dict[str, Any], Body()], db: Db, response: Response
    ) -> SessionOut:
        session_id = uuid.UUID(meta["session_id"])
        # ON CONFLICT makes concurrent replays safe: only one request inserts, the
        # others wait for it and then see the committed row.
        inserted = db.execute(
            pg_insert(Session)
            .values(
                id=session_id,
                platform=meta["platform"],
                device_model=meta["device_model"],
                os_version=meta["os_version"],
                meta=meta,
            )
            .on_conflict_do_nothing(index_elements=[Session.id])
            .returning(Session.id)
        ).scalar_one_or_none()

        if inserted is None:
            existing = db.get_one(Session, session_id)
            if existing.meta != meta:
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
                        "status": "expected",
                    }
                    for f in meta["files"]
                ],
            )
            db.commit()

        session = db.get_one(Session, session_id)
        return SessionOut.from_model(session)

    return app
