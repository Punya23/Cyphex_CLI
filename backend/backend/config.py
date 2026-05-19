"""
CYPHEX — Configuration
All settings centralized here. Uses environment variables with fallbacks.
"""

import os
from dataclasses import dataclass


@dataclass
class CyphexConfig:
    """Central configuration for CYPHEX."""

    # AI Backend Mode: 'local' (Ollama) | 'groq' (cloud) | 'cerebras' (legacy)
    # 'local' = primary (uses your GPU, no API key needed)
    # 'groq'  = cloud backup (free, fastest cloud API)
    AI_BACKEND_MODE: str = "local"

    # ─── Groq AI (Cloud — FREE, OpenAI-compatible) ───
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_MAX_TOKENS: int = 4096
    GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"

    # ─── Local Ollama (Primary — runs on your GPU) ───
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5-coder:7b"  # Best coding model you have installed

    # ─── Cerebras AI (Cloud — LEGACY, currently broken) ───
    CEREBRAS_API_KEY: str = ""  # Set via CEREBRAS_API_KEY env var
    CEREBRAS_MODEL: str = "llama-3.3-70b"
    CEREBRAS_MAX_TOKENS: int = 4096
    CEREBRAS_API_URL: str = "https://api.cerebras.ai/v1/chat/completions"

    # ─── Scan settings ───
    SCAN_TIMEOUT_SECONDS: int = 1800  # 30 minutes max
    COMMAND_TIMEOUT_SECONDS: int = 60  # Per-command default timeout
    MAX_PARALLEL_AGENTS: int = 6

    # ─── Immune System / Co-Evolution ───
    GENOME_BLOCK_THRESHOLD: float = 0.7      # Anomaly score above this = BLOCK
    EVOLUTION_GENERATIONS: int = 10           # Default generations per run
    EVOLUTION_PAYLOADS_PER_GEN: int = 20      # Payloads per generation
    GENOME_STORAGE_DIR: str = ""              # Where to save genome state
    EVOLUTION_CONVERGENCE_THRESHOLD: float = 0.99

    # ─── Paths ───
    WORKING_DIR: str = ""  # Set at runtime
    WORDLIST_DIR: str = ""  # Auto-detected

    # ─── Platform detection ───
    IS_WINDOWS: bool = os.name == "nt"
    SHELL: str = "powershell" if os.name == "nt" else "/bin/bash"

    def __post_init__(self):
        # Override from env if available
        self.AI_BACKEND_MODE = os.getenv("AI_BACKEND_MODE", self.AI_BACKEND_MODE)
        self.GROQ_API_KEY = os.getenv("GROQ_API_KEY", self.GROQ_API_KEY)
        self.CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", self.CEREBRAS_API_KEY)
        self.OLLAMA_URL = os.getenv("OLLAMA_URL", self.OLLAMA_URL)
        self.OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", self.OLLAMA_MODEL)

        # Set working dir
        if not self.WORKING_DIR:
            self.WORKING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "workdir")
            os.makedirs(self.WORKING_DIR, exist_ok=True)

        # Set genome storage dir
        if not self.GENOME_STORAGE_DIR:
            self.GENOME_STORAGE_DIR = os.path.join(self.WORKING_DIR, "genomes")
            os.makedirs(self.GENOME_STORAGE_DIR, exist_ok=True)


# Global config singleton
config = CyphexConfig()
