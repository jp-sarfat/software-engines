"""
QUBO encoder – encodes various problem types into QUBO format.
"""

from __future__ import annotations

import logging
from typing import Any, Tuple

import numpy as np
from numpy.typing import NDArray

from engines.quantum.encoders.base import BaseEncoder
from engines.quantum.problem import Problem, ProblemType, ObjectiveType

logger = logging.getLogger(__name__)


class QUBOEncoder(BaseEncoder):
    DEFAULT_PENALTY = 10.0

    def encode(self, problem: Problem) -> dict[str, Any]:
        dispatch = {
            ProblemType.QUBO: self._encode_qubo,
            ProblemType.ISING: self._encode_ising,
            ProblemType.MAXCUT: self._encode_maxcut,
            ProblemType.TSP: self._encode_tsp,
            ProblemType.SCHEDULING: self._encode_scheduling,
            ProblemType.RESOURCE_ALLOCATION: self._encode_scheduling,
        }
        encoder_fn = dispatch.get(problem.problem_type)
        if encoder_fn is None:
            raise ValueError(f"Unsupported problem type: {problem.problem_type}")
        return encoder_fn(problem)

    def decode(self, solution: Any, problem: Problem) -> dict[str, Any]:
        arr = np.array(solution) if not isinstance(solution, np.ndarray) else solution
        result: dict[str, Any] = {
            "raw_solution": arr,
            "selected_indices": np.where(arr == 1)[0].tolist(),
            "num_selected": int(np.sum(arr)),
        }
        if problem.problem_type == ProblemType.TSP:
            result["tour"] = self._decode_tsp(arr, problem)
        Q = problem.to_qubo_matrix()
        result["objective_value"] = float(arr @ Q @ arr)
        return result

    # ---- Encoders ----

    def _encode_qubo(self, problem: Problem) -> dict[str, Any]:
        Q = problem.to_qubo_matrix()
        n = Q.shape[0]
        if problem.objective == ObjectiveType.MAXIMIZE:
            Q = -Q
        return {
            "qubo_matrix": Q,
            "qubo_dict": self._matrix_to_dict(Q),
            "num_variables": n,
            "variable_names": [v.name for v in problem.variables],
            "offset": 0.0,
        }

    def _encode_ising(self, problem: Problem) -> dict[str, Any]:
        h = problem.ising_h
        J = problem.ising_j
        n = len(h)  # type: ignore[arg-type]
        Q = np.zeros((n, n))
        offset = 0.0
        for i in range(n):
            Q[i, i] = 2 * h[i]  # type: ignore[index]
            offset -= h[i]  # type: ignore[index]
        for (i, j), jval in J.items():  # type: ignore[union-attr]
            Q[i, j] += 4 * jval
            Q[i, i] -= 2 * jval
            Q[j, j] -= 2 * jval
            offset += jval
        return {
            "qubo_matrix": Q,
            "qubo_dict": self._matrix_to_dict(Q),
            "num_variables": n,
            "variable_names": [f"s_{i}" for i in range(n)],
            "offset": offset,
        }

    def _encode_maxcut(self, problem: Problem) -> dict[str, Any]:
        graph = problem.graph
        if graph is None:
            raise ValueError("MaxCut problem requires a graph")
        n = graph.number_of_nodes()
        Q = np.zeros((n, n))
        node_to_idx = {node: i for i, node in enumerate(graph.nodes())}
        for u, v, data in graph.edges(data=True):
            w = data.get("weight", 1.0)
            i, j = node_to_idx[u], node_to_idx[v]
            Q[i, i] += w
            Q[j, j] += w
            Q[i, j] -= 2 * w
        Q = -Q
        return {
            "qubo_matrix": Q,
            "qubo_dict": self._matrix_to_dict(Q),
            "num_variables": n,
            "variable_names": [f"node_{nd}" for nd in graph.nodes()],
            "offset": 0.0,
            "node_mapping": node_to_idx,
        }

    def _encode_tsp(self, problem: Problem) -> dict[str, Any]:
        D = problem.distance_matrix
        if D is None:
            raise ValueError("TSP problem requires distance_matrix")
        n = D.shape[0]
        num_vars = n * n
        Q = np.zeros((num_vars, num_vars))
        penalty = self.DEFAULT_PENALTY * np.max(D)

        def idx(city: int, t: int) -> int:
            return city * n + t

        for i in range(n):
            for t1 in range(n):
                Q[idx(i, t1), idx(i, t1)] -= penalty
                for t2 in range(t1, n):
                    if t1 == t2:
                        Q[idx(i, t1), idx(i, t1)] += penalty
                    else:
                        Q[idx(i, t1), idx(i, t2)] += 2 * penalty
        for t in range(n):
            for i1 in range(n):
                Q[idx(i1, t), idx(i1, t)] -= penalty
                for i2 in range(i1, n):
                    if i1 == i2:
                        Q[idx(i1, t), idx(i1, t)] += penalty
                    else:
                        Q[idx(i1, t), idx(i2, t)] += 2 * penalty
        for i in range(n):
            for j in range(n):
                if i != j:
                    for t in range(n):
                        nt = (t + 1) % n
                        Q[idx(i, t), idx(j, nt)] += D[i, j]
        return {
            "qubo_matrix": Q,
            "qubo_dict": self._matrix_to_dict(Q),
            "num_variables": num_vars,
            "variable_names": [f"city_{i}_time_{t}" for i in range(n) for t in range(n)],
            "offset": 2 * n * penalty,
            "num_cities": n,
        }

    def _encode_scheduling(self, problem: Problem) -> dict[str, Any]:
        data = problem.data
        if data is None or "jobs" not in data or "resources" not in data:
            raise ValueError("Scheduling problem requires jobs and resources data")
        jobs = data["jobs"]
        resources = data["resources"]
        nj, nr = len(jobs), len(resources)
        nt = max(j.get("deadline", 10) for j in jobs)
        num_vars = nj * nr * nt
        Q = np.zeros((num_vars, num_vars))
        penalty = self.DEFAULT_PENALTY

        def idx(job: int, res: int, t: int) -> int:
            return job * (nr * nt) + res * nt + t

        for j in range(nj):
            for r1 in range(nr):
                for t1 in range(nt):
                    Q[idx(j, r1, t1), idx(j, r1, t1)] -= penalty
                    for r2 in range(r1, nr):
                        for t2 in range(t1 if r1 == r2 else 0, nt):
                            if r1 == r2 and t1 == t2:
                                Q[idx(j, r1, t1), idx(j, r1, t1)] += penalty
                            else:
                                Q[idx(j, r1, t1), idx(j, r2, t2)] += 2 * penalty
        for j in range(nj):
            for r in range(nr):
                for t in range(nt):
                    Q[idx(j, r, t), idx(j, r, t)] += t * 0.1
        return {
            "qubo_matrix": Q,
            "qubo_dict": self._matrix_to_dict(Q),
            "num_variables": num_vars,
            "variable_names": [
                f"job_{j}_res_{r}_time_{t}" for j in range(nj) for r in range(nr) for t in range(nt)
            ],
            "offset": nj * penalty,
            "num_jobs": nj,
            "num_resources": nr,
            "num_times": nt,
        }

    def _decode_tsp(self, solution: NDArray, problem: Problem) -> list[int]:
        D = problem.distance_matrix
        n = D.shape[0]  # type: ignore[union-attr]
        tour: list[int] = []
        for t in range(n):
            for i in range(n):
                if i * n + t < len(solution) and solution[i * n + t] == 1:
                    tour.append(i)
                    break
        return tour

    @staticmethod
    def _matrix_to_dict(Q: NDArray) -> dict[Tuple[int, int], float]:
        qubo_dict: dict[Tuple[int, int], float] = {}
        n = Q.shape[0]
        for i in range(n):
            for j in range(i, n):
                val = Q[i, j] if i == j else Q[i, j] + Q[j, i]
                if val != 0:
                    qubo_dict[(i, j)] = val
        return qubo_dict

    def validate(self, problem: Problem) -> list[str]:
        supported = {
            ProblemType.QUBO, ProblemType.ISING, ProblemType.MAXCUT,
            ProblemType.TSP, ProblemType.SCHEDULING, ProblemType.RESOURCE_ALLOCATION,
        }
        errors: list[str] = []
        if problem.problem_type not in supported:
            errors.append(f"Problem type {problem.problem_type} not supported by QUBO encoder")
        if problem.problem_type == ProblemType.MAXCUT and problem.graph is None:
            errors.append("MaxCut requires a graph")
        if problem.problem_type == ProblemType.TSP and problem.distance_matrix is None:
            errors.append("TSP requires a distance matrix")
        return errors
