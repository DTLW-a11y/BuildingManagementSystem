"""
建筑能源智能管理系统 - 后端主应用
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import init_db
from routers import data, query, statistics, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    init_db()
    yield


app = FastAPI(
    title="建筑能源智能管理系统",
    description=(
        "基于大模型技术的建筑能源智能管理与运营优化平台，"
        "提供能耗数据查询统计、智慧运维问答等功能。"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS配置（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(data.router)
app.include_router(query.router)
app.include_router(statistics.router)
app.include_router(chat.router)

# 挂载前端静态文件（Vue dist 优先，回退到旧版 frontend/）
_FRONTEND_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "..", "frontend-vue", "dist"),
    os.path.join(os.path.dirname(__file__), "..", "frontend"),
]
FRONTEND_DIR = next((d for d in _FRONTEND_CANDIDATES if os.path.exists(d)), None)

def _safe_local_path(base_dir: str, path: str) -> str:
    normalized = os.path.normpath(path).lstrip(os.sep).lstrip("./")
    if normalized.startswith(".."):
        raise HTTPException(status_code=404, detail="Not found")
    return os.path.join(base_dir, normalized)


def _serve_frontend_file(subdir: str, path: str) -> FileResponse:
    if FRONTEND_DIR:
        dist_path = _safe_local_path(os.path.join(FRONTEND_DIR, subdir), path)
        if os.path.isfile(dist_path):
            return FileResponse(dist_path)

    public_dir = os.path.join(os.path.dirname(__file__), "..", "frontend-vue", "public", subdir)
    public_path = _safe_local_path(public_dir, path)
    if os.path.isfile(public_path):
        return FileResponse(public_path)

    raise HTTPException(status_code=404, detail="Not found")


if FRONTEND_DIR:
    _assets_dir = os.path.join(FRONTEND_DIR, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/image/{path:path}", include_in_schema=False)
    def serve_image(path: str):
        return _serve_frontend_file("image", path)

    @app.get("/background/{path:path}", include_in_schema=False)
    def serve_background(path: str):
        return _serve_frontend_file("background", path)

    @app.get("/", include_in_schema=False)
    def serve_index():
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        return FileResponse(index_path)


@app.get("/health", tags=["系统"])
def health_check():
    return {"status": "ok", "message": "建筑能源智能管理系统运行正常"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
