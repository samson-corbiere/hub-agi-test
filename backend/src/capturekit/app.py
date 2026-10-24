"""The CaptureKit ingest API."""

from fastapi import FastAPI


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="CaptureKit ingest API")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
