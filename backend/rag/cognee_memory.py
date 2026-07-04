"""
CYPHEX — Cross-project patch memory via cognee (optional).

Unlike backend/rag/patch_memory.py (an exact cwe:hash cache scoped to one
project), this module lets a patch strategy learned fixing a vulnerability
in one project transfer to a semantically-similar one in an unrelated
project, by storing verified fixes in a local knowledge graph and querying
it semantically before generating a new patch.

This is the ONLY module that imports `cognee` directly — every other part
of the codebase goes through the narrow functions below, so a breaking
change in cognee's (beta-stage) API only ever needs a fix here.

Fully local by design: no Neo4j/cloud server, no OpenAI key, no network
calls beyond the developer's own Ollama instance. `cognee` ships an
anonymous telemetry call to an external endpoint by default — disabled
unconditionally below, before anything else happens in this module.
"""

import asyncio
import importlib.util
import os

from backend.reasoning.session_memory import _CYPHEX_ROOT, _repo_hash

# Must happen before `import cognee` anywhere, including inside this module's
# own lazy _ensure_configured() — set at module load, not deferred, as
# defense-in-depth (cheap, no reason to delay it).
os.environ.setdefault("TELEMETRY_DISABLED", "1")

# Cheap check only — no actual import. cognee's dependency footprint (~39
# packages incl. fastapi/sqlalchemy/lancedb) is heavy enough that eagerly
# importing it would tax every CLI invocation, not just patch runs.
COGNEE_AVAILABLE = importlib.util.find_spec("cognee") is not None

# One fixed, shared dataset across every project — never per-project.
# cognee's dataset_name is a multi-tenant *segregation* primitive; using one
# per project would just reimplement patch_memory.py's exact-scoping limits
# inside cognee and defeat the point of this module (cross-project recall).
DATASET_NAME = "cyphex_patch_memory"

# Stable global directory, outside any scanned/cloned repo — mirrors
# backend/reasoning/session_memory.py's SESSION_DIR pattern, so memory
# persists across different sandboxes/clones of the same project.
COGNEE_DATA_DIR = os.path.join(_CYPHEX_ROOT, ".cognee_data")

_configured = False


def is_available() -> bool:
    return COGNEE_AVAILABLE


def project_id_for(repo_url: str, source_dir: str) -> str:
    """Stable cross-scan project identity — reuses session_memory's scheme."""
    identifier = (repo_url or source_dir or "unknown").rstrip("/").removesuffix(".git")
    return _repo_hash(identifier)


def _ensure_configured() -> bool:
    """
    Lazily configure cognee for a fully local, Ollama-backed setup and import
    it. Runs once; returns False (without raising) if cognee can't be
    configured for any reason, so callers can no-op instead of crashing the
    patch pipeline.

    Uses cognee's `cognee.config.set_*()` API rather than only environment
    variables. cognee caches its settings objects with `@lru_cache` on first
    access — if *anything* in the process imports `cognee` before this
    function runs (e.g. another module, or a test's `pytest.importorskip`),
    env vars set afterward are silently ignored because the cached config
    was already built from the environment at that earlier point. The
    `config.set_*()` calls mutate the same live cached objects directly, so
    they take effect regardless of when cognee was first imported.
    """
    global _configured
    if _configured:
        return True
    if not COGNEE_AVAILABLE:
        return False

    try:
        from backend.backend.config import config as cyphex_config

        os.makedirs(COGNEE_DATA_DIR, exist_ok=True)

        # CYPHEX is a single-user local CLI tool — cognee's multi-user
        # access control is irrelevant overhead, and (as of 1.2.2) its
        # default dataset-to-database handler ("ladybug") isn't compatible
        # with the kuzu graph provider used here, which would otherwise
        # raise on every remember()/recall() call. Read live via os.environ
        # at call time (not cached), so setting it here is reliable
        # regardless of when cognee was first imported.
        os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")

        # Harmless defense-in-depth for any code path that reads env vars
        # directly instead of going through cognee.config — but not relied
        # on alone, see docstring above.
        os.environ.setdefault("LLM_PROVIDER", "ollama")
        os.environ.setdefault("LLM_MODEL", cyphex_config.COGNEE_LLM_MODEL or cyphex_config.OLLAMA_MODEL)
        os.environ.setdefault("LLM_ENDPOINT", f"{cyphex_config.OLLAMA_URL}/v1")
        os.environ.setdefault("LLM_API_KEY", "ollama")  # dummy value — no real key needed for Ollama
        os.environ.setdefault("EMBEDDING_PROVIDER", "ollama")
        os.environ.setdefault("EMBEDDING_MODEL", cyphex_config.COGNEE_EMBEDDING_MODEL)
        os.environ.setdefault("EMBEDDING_ENDPOINT", f"{cyphex_config.OLLAMA_URL}/api/embed")
        os.environ.setdefault("EMBEDDING_DIMENSIONS", "768")

        import cognee

        # Authoritative — mutates the live (possibly already-cached) config
        # objects directly, so this always wins regardless of import order.
        cognee.config.set_vector_db_provider("lancedb")
        cognee.config.set_graph_database_provider("kuzu")
        # Cascades to derive the lancedb/kuzu file paths under this directory.
        cognee.config.system_root_directory(COGNEE_DATA_DIR)
        cognee.config.data_root_directory(COGNEE_DATA_DIR)

        cognee.config.set_llm_provider("ollama")
        cognee.config.set_llm_model(cyphex_config.COGNEE_LLM_MODEL or cyphex_config.OLLAMA_MODEL)
        cognee.config.set_llm_endpoint(f"{cyphex_config.OLLAMA_URL}/v1")
        cognee.config.set_llm_api_key("ollama")  # dummy value — no real key needed for Ollama

        cognee.config.set_embedding_provider("ollama")
        cognee.config.set_embedding_model(cyphex_config.COGNEE_EMBEDDING_MODEL)
        cognee.config.set_embedding_endpoint(f"{cyphex_config.OLLAMA_URL}/api/embed")
        cognee.config.set_embedding_dimensions(768)
        # OllamaEmbeddingEngine uses a HuggingFace tokenizer for local token
        # counting (not for the embedding call itself, which stays on
        # Ollama) — it isn't optional, and cognee's default is None, which
        # crashes. A small, ungated, widely-cached model is enough for this.
        cognee.config.set_embedding_config({"huggingface_tokenizer": "bert-base-uncased"})

        _configured = True
        return True
    except Exception:
        return False


def _format_content(cwe: str, vulnerable_code: str, fixed_code: str, project_id: str, framework: str) -> str:
    """
    Structured text blob for cognee to ingest. Project/CWE/framework
    attribution is embedded as plain text rather than a "tag"/node_set API —
    that keeps this stable across cognee's beta-stage API churn, since it's
    just prompt text cognee will chunk/extract entities from regardless of
    version, rather than a version-fragile metadata call.
    """
    lines = [
        f"project_id: {project_id}",
        f"cwe: {cwe}",
    ]
    if framework:
        lines.append(f"framework: {framework}")
    lines.append("")
    lines.append("vulnerable code:")
    lines.append(vulnerable_code)
    lines.append("")
    lines.append("verified fix:")
    lines.append(fixed_code)
    return "\n".join(lines)


async def remember_fix(cwe: str, vulnerable_code: str, fixed_code: str, project_id: str, framework: str = "") -> None:
    """
    Persist a verified fix into the shared cross-project memory graph.
    Never raises — callers should still bound this with asyncio.wait_for(),
    since cognee's cognify step runs an LLM entity-extraction pass and can
    be slow.

    Uses the low-level add()+cognify() pipeline rather than the newer
    remember() convenience wrapper: as of cognee 1.2.2, remember() hits an
    internal MigrationError the moment ENABLE_BACKEND_ACCESS_CONTROL=false
    (required — see _ensure_configured) combined with a fresh/global
    database, because it always routes through cognee's multi-user
    migration bookkeeping regardless of whether access control is actually
    in use. add()+cognify() is cognee's own documented "V1 API — still
    works" path and doesn't hit this in testing.
    """
    if not _ensure_configured():
        return

    import cognee

    content = _format_content(cwe, vulnerable_code, fixed_code, project_id, framework)

    try:
        await cognee.add(content, dataset_name=DATASET_NAME)
        await cognee.cognify(datasets=[DATASET_NAME])
    except Exception:
        return


async def recall_similar_fixes(cwe: str, vulnerable_code: str, limit: int = 3) -> list:
    """
    Query the shared memory graph for fixes to similar vulnerabilities,
    across any project. Always returns a list — [] on cognee not being
    installed/configured, an empty graph, a timeout, or any error; never
    raises and never returns None, so callers can treat the result as
    "no hint" with no special-casing.

    Uses cognee's low-level search() rather than the newer recall()
    wrapper, for the same reason remember_fix() uses add()+cognify() — see
    that function's docstring.
    """
    if not _ensure_configured():
        return []

    import cognee
    from cognee import SearchType

    query = f"How was a {cwe} vulnerability fixed in code similar to:\n{vulnerable_code}"

    try:
        results = await cognee.search(
            query_type=SearchType.GRAPH_COMPLETION,
            query_text=query,
            datasets=[DATASET_NAME],
        )

        if not results:
            return []
        if isinstance(results, list):
            return results[:limit]
        return [results]
    except Exception:
        return []


def format_hint(hits: list) -> str:
    """Empty string for an empty/falsy hits list; otherwise a MEMORY HINT prompt block."""
    if not hits:
        return ""
    joined = "\n---\n".join(str(h) for h in hits)
    return (
        "MEMORY HINT — similar vulnerabilities fixed in other projects "
        "(use as a reference, adapt to this codebase's actual style):\n"
        f"{joined}"
    )
