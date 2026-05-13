"""
CYPHEX — Agent Result & Terminal Output Models
Every command executed by any agent produces a TerminalOutput.
Every agent run produces an AgentResult.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class TerminalOutput:
    """Result of a single terminal command execution."""
    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    @property
    def combined(self) -> str:
        return self.stdout + self.stderr

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "stdout": self.stdout[:2000],  # Truncate for serialization
            "stderr": self.stderr[:1000],
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
        }


@dataclass
class AgentResult:
    """Result produced by a single agent run."""
    agent: str
    vulns: list = field(default_factory=list)
    context: Any = None
    report: Optional[dict] = None
    cure_plan: Optional[dict] = None
    terminal_logs: list = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "vulns_found": len(self.vulns),
            "vulns": [v.to_dict() if hasattr(v, 'to_dict') else str(v) for v in self.vulns],
            "report": self.report,
            "cure_plan": self.cure_plan,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "terminal_commands_run": len(self.terminal_logs),
        }
