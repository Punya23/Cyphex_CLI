"""
CYPHEX patch pipeline.

Modules:
  resolver  — turn a Vuln.endpoint into a concrete Location (file:line or url)
  applier   — range-accurate, reversible application of a fixed code block
  verifier  — the verification gate (static re-scan + dynamic replay + guards)
  manifest  — durable .cyphex/patches.json + honest, verified-only scoring

Phase 3+ will add: templates, regression.
"""

from backend.patch.resolver import Location, resolve
from backend.patch.applier import PatchApplier, ApplyResult
from backend.patch.verifier import (
    VerifyResult, verify_static, verify_dynamic,
    check_suppression, check_blast_radius,
    PASS, FAIL, UNVERIFIABLE,
)
from backend.patch.manifest import PatchManifest, PatchRecord, sha256
from backend.patch import templates
from backend.patch.patch_memory import PatchMemory, semantic_hash
from backend.patch.regression import emit_dynamic_regression_test, emit_static_regression_note

__all__ = [
    "Location", "resolve",
    "PatchApplier", "ApplyResult",
    "VerifyResult", "verify_static", "verify_dynamic",
    "check_suppression", "check_blast_radius",
    "PASS", "FAIL", "UNVERIFIABLE",
    "PatchManifest", "PatchRecord", "sha256",
    "templates",
    "PatchMemory", "semantic_hash",
    "emit_dynamic_regression_test", "emit_static_regression_note",
]
