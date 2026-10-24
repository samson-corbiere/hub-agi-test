"""The CaptureKit ingest API."""

from fastapi import FastAPI


def create_app(database_url: str | None = None) -> FastAPI:
    return FastAPI(title="CaptureKit ingest API")
