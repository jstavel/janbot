"""FastAPI application for JanBot."""

from fastapi import FastAPI

app = FastAPI(title="JanBot")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
