"""ctx_for_tier() bounds PROMPT + OUTPUT together for every Ollama call —
patch generation, review, debate. A live scan showed 9 of 12 patches coming
back "invalid syntax — auto-rolled back": a RAG-enriched patch-generation
prompt (full function body + imports + CWE recipe + secure example) can run
2500-3500 tokens on its own, and the old uniform num_ctx=4096 for
mid/low/minimal/cloud tiers left the model almost no room to emit its own
fix before getting cut off mid-function. Only the cyphex-patch fine-tune
genuinely needs the 4096 cap (its own training context); every other model
in this pipeline (qwen2.5-coder, llama3.1, deepseek-coder) natively supports
far more.
"""
from unittest.mock import patch

from backend.council.council_orchestrator import ctx_for_tier


def _mode(name):
    return patch("cyphex.hardware.detect_mode", return_value=name)


def test_cyphex_patch_model_keeps_its_trained_4096_context():
    with _mode("ultra"):
        cfg = ctx_for_tier("cyphex-patch")
    assert cfg == {"num_ctx": 4096, "num_predict": 2048}


def test_cyphex_patch_match_is_case_and_tag_insensitive():
    with _mode("ultra"):
        assert ctx_for_tier("CYPHEX-PATCH:latest")["num_ctx"] == 4096


def test_other_models_get_the_larger_tier_budget_not_the_old_4096_cap():
    with _mode("mid"):
        cfg = ctx_for_tier("qwen2.5-coder:7b")
    assert cfg["num_ctx"] > 4096
    assert cfg["num_predict"] > 1024


def test_every_non_cyphex_patch_tier_has_headroom_beyond_a_typical_rag_prompt():
    """The real failure mode this pins: num_ctx must comfortably exceed a
    ~3000-token RAG-enriched prompt AND still leave room for the model's own
    output, for every tier — not just the top one."""
    for mode in ("ultra", "high", "mid", "low", "minimal", "cloud"):
        with _mode(mode):
            cfg = ctx_for_tier("qwen2.5-coder:7b")
        assert cfg["num_ctx"] >= 6144, f"{mode} tier's num_ctx too tight for a RAG-enriched prompt"
        assert cfg["num_ctx"] > cfg["num_predict"] + 3000, (
            f"{mode} tier leaves no room for a ~3000-token prompt alongside its own num_predict budget"
        )


def test_unknown_or_undetectable_hardware_falls_back_to_mid_safely():
    with patch("cyphex.hardware.detect_mode", side_effect=Exception("boom")):
        cfg = ctx_for_tier("qwen2.5-coder:7b")
    assert cfg["num_ctx"] >= 6144  # falls back to "mid", not a crash
