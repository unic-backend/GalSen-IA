"""
Integration layer for GalSen IA.

This package wires the independent engines together. It owns no business logic:
its only responsibility is to make every engine reachable from one place, so
agents can use them without knowing how they are built.
"""

from .engine_registry import (
    ENGINE_NAMES,
    EngineRegistry,
    EngineUnavailableError,
    get_shared_registry,
)

__all__ = [
    "ENGINE_NAMES",
    "EngineRegistry",
    "EngineUnavailableError",
    "get_shared_registry",
]
