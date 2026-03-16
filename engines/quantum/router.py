"""
FastAPI router for the Quantum engine.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import numpy as np

from engines.quantum.bridge import QuantumBridge
from engines.quantum.problem import Problem, ObjectiveType
from engines.quantum.config import QuantumConfig, ProviderType

router = APIRouter(prefix="/quantum", tags=["Quantum"])

_bridge = QuantumBridge(config=QuantumConfig.for_local_development())


# ---- Request / response models ----

class QUBORequest(BaseModel):
    name: str = "QUBO Problem"
    qubo_matrix: list[list[float]] = Field(..., description="QUBO matrix as 2D array")
    objective: str = "minimize"
    timeout_seconds: float = 300
    force_classical: bool = False


class MaxCutRequest(BaseModel):
    name: str = "MaxCut Problem"
    edges: list[list[int | float]] = Field(..., description="Edges as [u, v] or [u, v, weight]")
    num_nodes: int
    timeout_seconds: float = 300


class TSPRequest(BaseModel):
    name: str = "TSP Problem"
    distance_matrix: list[list[float]]
    timeout_seconds: float = 300


class SolutionResponse(BaseModel):
    status: str
    solution: Optional[list[int]] = None
    solution_dict: Optional[dict[str, int]] = None
    energy: Optional[float] = None
    objective_value: Optional[float] = None
    solver_type: str
    solver_name: str
    total_time_ms: float
    is_quantum: bool
    confidence: float
    selected_indices: list[int] = []
    metadata: dict[str, Any] = {}


class StatusResponse(BaseModel):
    mode: str
    default_provider: str
    budget_remaining_usd: float
    budget_remaining_time_seconds: float
    budget_usage_percentage: float


def _to_response(result) -> SolutionResponse:
    return SolutionResponse(
        status=result.status.value,
        solution=result.solution.tolist() if result.solution is not None else None,
        solution_dict=result.solution_dict or None,
        energy=result.quality.energy,
        objective_value=result.quality.objective_value,
        solver_type=result.solver_type.value,
        solver_name=result.solver_name,
        total_time_ms=result.timing.total_time_ms,
        is_quantum=result.is_quantum,
        confidence=result.quality.confidence,
        selected_indices=result.get_selected_indices(),
        metadata=result.summary(),
    )


@router.get("/status", response_model=StatusResponse)
async def quantum_status():
    s = _bridge.get_status()
    return StatusResponse(
        mode=s["mode"],
        default_provider=s["default_provider"],
        budget_remaining_usd=s["budget"]["remaining_usd"],
        budget_remaining_time_seconds=s["budget"]["remaining_time_seconds"],
        budget_usage_percentage=s["budget"]["usage_percentage"],
    )


@router.post("/solve/qubo", response_model=SolutionResponse)
async def solve_qubo(req: QUBORequest):
    try:
        Q = np.array(req.qubo_matrix)
        obj = ObjectiveType.MINIMIZE if req.objective == "minimize" else ObjectiveType.MAXIMIZE
        problem = Problem.from_qubo_matrix(Q, name=req.name, objective=obj)
        result = _bridge.solve(
            problem,
            force_classical=req.force_classical,
            timeout_seconds=req.timeout_seconds,
        )
        return _to_response(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/solve/maxcut", response_model=SolutionResponse)
async def solve_maxcut(req: MaxCutRequest):
    try:
        import networkx as nx

        G = nx.Graph()
        G.add_nodes_from(range(req.num_nodes))
        for edge in req.edges:
            if len(edge) == 2:
                G.add_edge(int(edge[0]), int(edge[1]), weight=1.0)
            else:
                G.add_edge(int(edge[0]), int(edge[1]), weight=float(edge[2]))
        problem = Problem.from_maxcut(G, name=req.name)
        result = _bridge.solve(problem, timeout_seconds=req.timeout_seconds)
        return _to_response(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/solve/tsp", response_model=SolutionResponse)
async def solve_tsp(req: TSPRequest):
    try:
        D = np.array(req.distance_matrix)
        problem = Problem.from_tsp(D, name=req.name)
        result = _bridge.solve(problem, timeout_seconds=req.timeout_seconds)
        return _to_response(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-budget")
async def reset_budget():
    _bridge.reset_budget()
    return {"status": "ok", "message": "Budget counters reset"}
