"""finetune/eval.py must parse and keep its 50/30/20 prompt mix.

The file once closed its prompt list after each group (`] * 10,`), leaving the
later groups outside any bracket: an IndentationError that failed CI's
syntax gate on every platform. Loading it here fails the same way, earlier.
"""
import importlib.util
from pathlib import Path

EVAL_PY = Path(__file__).resolve().parent.parent / "finetune" / "eval.py"


def test_eval_prompts_are_100_in_a_50_30_20_mix():
    spec = importlib.util.spec_from_file_location("finetune_eval", EVAL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    prompts = mod.TEST_PROMPTS
    assert len(prompts) == 100
    safe = [p for p in prompts if p.startswith("Is this code vulnerable?")]
    vuln = [p for p in prompts if p.startswith("Identify security vulnerabilities")]
    assert (len(safe), len(vuln), len(prompts) - len(safe) - len(vuln)) == (50, 30, 20)
