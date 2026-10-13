from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS
from .db import init_db
from .routes import router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"  # React build is copied here in Docker


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="StayFlow API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        # Serve the single-page app for any non-API route.
        return FileResponse(STATIC_DIR / "index.html")
