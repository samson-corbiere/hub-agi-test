"""The CaptureKit ingest API."""

from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, status
from sqlalchemy import create_engine
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

    @app.post("/sessions", status_code=status.HTTP_201_CREATED)
    def register_session(meta: Annotated[dict[str, Any], Body()], db: Db) -> SessionOut:
        session = Session(
            id=meta["session_id"],
            platform=meta["platform"],
            device_model=meta["device_model"],
            os_version=meta["os_version"],
            meta=meta,
            files=[
                SessionFile(name=f["name"], size=f["size"], sha256=f["sha256"], status="expected")
                for f in meta["files"]
            ],
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return SessionOut.from_model(session)

    return app
