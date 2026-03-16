"""
Quantum Engine
==============

Quantum-classical optimization bridge ported from the Quantum project.
Provides QUBO, MaxCut, TSP, and scheduling solvers with automatic
fallback to classical methods.
"""

from engines.quantum.bridge import QuantumBridge
from engines.quantum.problem import Problem, ProblemType
from engines.quantum.result import QuantumResult
from engines.quantum.config import QuantumConfig

__all__ = ["QuantumBridge", "Problem", "ProblemType", "QuantumResult", "QuantumConfig"]
