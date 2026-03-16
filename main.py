"""
Software Engines – Unified FastAPI application.

The mastermind.  All programs connect here.

Engines:
  /persona   – Qyvella: AI reasoning companion
  /hub       – Integration hub: service registry, events, commands
  /analysis  – Dual Claude codebase analysis
  /quantum   – Quantum-classical optimization bridge
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from engines.persona.router import router as persona_router
from engines.hub.router import router as hub_router
from engines.analysis.router import router as analysis_router
from engines.quantum.router import router as quantum_router

app = FastAPI(
    title="Software Engines",
    description=(
        "The mastermind API suite.  Qyvella (AI reasoning companion), "
        "Integration Hub (service registry & dispatch), "
        "Analysis engine (dual-Claude codebase analysis), and "
        "Quantum engine (quantum-classical optimization bridge).  "
        "All external programs connect via /hub."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(persona_router)
app.include_router(hub_router)
app.include_router(analysis_router)
app.include_router(quantum_router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "name": "Software Engines",
        "version": "0.2.0",
        "engines": ["persona", "hub", "analysis", "quantum"],
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
