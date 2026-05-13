"""
CYPHEX — Quick Test: Adversarial Co-Evolution Engine

Tests the immune system without needing a real target.
Uses simulated scan context to verify all components work.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "backend"))

from models.scan import ScanContext, FormData, ParamData
from immune.evolution_controller import EvolutionController


async def test_evolution():
    """Run a quick co-evolution test with simulated scan data."""

    print("=" * 60)
    print("  CYPHEX Adversarial Co-Evolution Engine — Test")
    print("=" * 60)

    # Create simulated scan context (as if agents already scanned)
    context = ScanContext(
        target_url="http://vulncorp.local:5000",
        framework="Flask",
        database="SQLite",
        os_type="Linux",
        all_endpoints=[
            "http://vulncorp.local:5000/api/search",
            "http://vulncorp.local:5000/api/login",
            "http://vulncorp.local:5000/api/users",
            "http://vulncorp.local:5000/api/profile",
        ],
        all_forms=[
            FormData(
                action="http://vulncorp.local:5000/api/login",
                method="POST",
                inputs=["username", "password"],
            ),
            FormData(
                action="http://vulncorp.local:5000/api/search",
                method="GET",
                inputs=["q"],
            ),
        ],
        all_params=[
            ParamData(url="http://vulncorp.local:5000/api/search", name="q", value="test"),
            ParamData(url="http://vulncorp.local:5000/api/users", name="id", value="1"),
        ],
    )

    # Run evolution
    controller = EvolutionController()

    results = await controller.run_evolution(
        context,
        generations=10,
        payloads_per_gen=20,
    )

    # Print summary
    summary = controller.get_evolution_summary()
    print("\n  📊 EVOLUTION SUMMARY:")
    print(f"  ├── Generations: {summary['generations_completed']}")
    print(f"  ├── Initial Block Rate: {summary['initial_block_rate']:.1%}")
    print(f"  ├── Final Block Rate: {summary['final_block_rate']:.1%}")
    print(f"  ├── Endpoints Profiled: {summary['genome_endpoints']}")
    print(f"  ├── Total Attacks Tested: {summary['total_attacks_tested']}")
    print(f"  └── Total Attacks Blocked: {summary['total_attacks_blocked']}")

    print("\n  📈 Block Rate Progression:")
    for r in summary['history']:
        bar_len = int(r['block_rate'] * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        print(f"    Gen {r['generation']:2d}: [{bar}] {r['block_rate']:.1%}  ({r['payloads_blocked']}/{r['payloads_generated']})")

    print("\n  ✅ All immune system components working!")
    return summary


if __name__ == "__main__":
    asyncio.run(test_evolution())
