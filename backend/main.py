"""
FastAPI entrypoint for AfyaDeploy.
Classical-first CHW deployment evaluation for rural Kenya; optional qBraid QAOA comparator.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router

app = FastAPI(
    title="AfyaDeploy API",
    description=(
        "Classical-first Community Health Worker deployment for rural Kenya. "
        "C1–C7 on local CPU; QAOA via free qBraid simulator as secondary comparator."
    ),
    version="3.0.0",
)

# Comma-separated origins for the Vercel dashboard, e.g.
# https://afyadeploy.vercel.app,http://localhost:5173
_cors = os.getenv("CORS_ORIGINS", "*").strip()
_allow_origins = [o.strip() for o in _cors.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {"service": "AfyaDeploy API", "docs": "/docs", "health": "/api/health"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
