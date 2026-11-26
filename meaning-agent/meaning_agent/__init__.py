"""Meaning Intelligence: deterministic, human-approved analysis scaffolding."""

__version__ = "1.0.0"

from .constants import SCHEMA_VERSION
from .engine import analyze, demo, review
from .rendering import to_markdown
from .skills.registry import registry_metadata

__all__ = [
    "analyze", "review", "demo", "to_markdown", "registry_metadata",
    "SCHEMA_VERSION", "__version__",
]
