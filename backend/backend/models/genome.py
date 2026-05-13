"""
CYPHEX — Genome Data Models

Data structures for the Behavioral Genome and Co-Evolution Engine.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class EndpointProfile:
    """Behavioral profile for a single endpoint."""
    endpoint: str                          # e.g., "/api/search"
    method: str                            # GET/POST
    input_fields: list[str] = field(default_factory=list)
    input_length_mean: float = 0.0
    input_length_std: float = 10.0
    input_charset_expected: str = "alphanumeric"  # alphanumeric | mixed | any
    input_entropy_mean: float = 3.0
    input_entropy_std: float = 0.5
    response_size_mean: float = 0.0
    response_time_mean_ms: float = 0.0
    sample_count: int = 0

    def to_dict(self) -> dict:
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "input_fields": self.input_fields,
            "input_length_mean": round(self.input_length_mean, 2),
            "input_length_std": round(self.input_length_std, 2),
            "input_entropy_mean": round(self.input_entropy_mean, 2),
            "sample_count": self.sample_count,
        }


@dataclass
class GenomeState:
    """Complete behavioral genome for an application."""
    target_url: str
    endpoints: dict = field(default_factory=dict)  # endpoint_key → EndpointProfile
    generation: int = 0
    block_rate: float = 0.0
    total_attacks_seen: int = 0
    total_attacks_blocked: int = 0
    created_at: str = ""
    last_evolved: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "target_url": self.target_url,
            "generation": self.generation,
            "block_rate": round(self.block_rate, 4),
            "total_attacks_seen": self.total_attacks_seen,
            "total_attacks_blocked": self.total_attacks_blocked,
            "endpoints_profiled": len(self.endpoints),
            "created_at": self.created_at,
            "last_evolved": self.last_evolved,
        }


@dataclass
class EvolutionResult:
    """Result of a single red-vs-blue generation."""
    generation: int
    payloads_generated: int = 0
    payloads_blocked: int = 0
    payloads_bypassed: int = 0
    block_rate: float = 0.0
    new_features_learned: list[str] = field(default_factory=list)
    red_mutations_applied: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "generation": self.generation,
            "payloads_generated": self.payloads_generated,
            "payloads_blocked": self.payloads_blocked,
            "payloads_bypassed": self.payloads_bypassed,
            "block_rate": round(self.block_rate, 4),
            "new_features_learned": self.new_features_learned,
            "red_mutations_applied": self.red_mutations_applied,
            "duration_seconds": round(self.duration_seconds, 2),
        }
