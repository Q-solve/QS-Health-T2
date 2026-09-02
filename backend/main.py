"""
FastAPI Main Application Entrypoint for AfyaDeploy Quantum.
Quantum-Optimized CHW Deployment in Rural Kenya synced with qBraid platform.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router

app = FastAPI(
    title="AfyaDeploy Quantum API",
    description="Quantum-optimized Community Health Worker (CHW) deployment system for rural Kenya via qBraid platform.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
