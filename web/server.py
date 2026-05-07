from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from web.routes.runs import router as runs_router

static_dir = Path(__file__).parent / "static"

app = FastAPI(title="SolutionArchitect")

app.include_router(runs_router, prefix="/api")

# Explicit root route — StaticFiles mount at "/" doesn't intercept bare "/"
@app.get("/")
async def index():
    return FileResponse(static_dir / "index.html")

# Serve all other static assets (js, css, etc.)
app.mount("/", StaticFiles(directory=static_dir), name="static")
