"""
CYPHEX patch pipeline.

Modules:
  resolver  — turn a Vuln.endpoint into a concrete Location (file:line or url)
  applier   — range-accurate, reversible application of a fixed code block

Phase 2+ will add: verifier, templates, manifest, regression.
"""

from backend.patch.resolver import Location, resolve
from backend.patch.applier import PatchApplier, ApplyResult

__all__ = ["Location", "resolve", "PatchApplier", "ApplyResult"]
