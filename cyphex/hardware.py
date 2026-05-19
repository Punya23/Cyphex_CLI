"""
CYPHEX CLI — Hardware Detection & Mode Selection

Detects available GPU VRAM and selects the appropriate operating mode:
- full:     6+ GB VRAM → all 4 council models
- standard: 4+ GB VRAM → phi3:mini + deepseek-coder:1.3b
- lite:     2+ GB VRAM → deepseek-coder:1.3b only
- cloud:    no GPU     → Groq/OpenAI cloud fallback
"""

import os
import shutil
import subprocess
import platform
from typing import Optional


def get_gpu_info() -> dict:
    """
    Detect GPU and available VRAM across platforms.
    Returns: {"gpu_name": str, "vram_gb": float, "platform": str}
    """
    system = platform.system().lower()
    info = {"gpu_name": "None", "vram_gb": 0.0, "platform": system}

    # ── NVIDIA (Windows/Linux) ──
    if shutil.which("nvidia-smi"):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                line = result.stdout.strip().split("\n")[0]
                parts = line.split(", ")
                if len(parts) == 2:
                    info["gpu_name"] = parts[0].strip()
                    info["vram_gb"] = round(int(parts[1].strip()) / 1024, 1)
                    return info
        except Exception:
            pass

    # ── Apple Silicon (macOS — unified memory) ──
    if system == "darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                total_bytes = int(result.stdout.strip())
                # Apple Silicon shares RAM with GPU; report ~75% as available for ML
                total_gb = total_bytes / (1024 ** 3)
                info["gpu_name"] = _get_apple_chip()
                info["vram_gb"] = round(total_gb * 0.75, 1)
                return info
        except Exception:
            pass

    # ── AMD ROCm (Linux) ──
    if shutil.which("rocm-smi"):
        try:
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "Total" in line:
                        # Parse total VRAM in MB
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if p.isdigit():
                                info["vram_gb"] = round(int(p) / 1024, 1)
                                info["gpu_name"] = "AMD GPU (ROCm)"
                                return info
        except Exception:
            pass

    return info


def _get_apple_chip() -> str:
    """Detect Apple Silicon chip model."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "Apple Silicon"


def detect_mode(vram_gb: Optional[float] = None) -> str:
    """
    Select operating mode based on available VRAM.

    Returns: 'full' | 'standard' | 'lite' | 'cloud'
    """
    if vram_gb is None:
        vram_gb = get_gpu_info()["vram_gb"]

    if vram_gb >= 6.0:
        return "full"       # All 4 council models
    elif vram_gb >= 4.0:
        return "standard"   # phi3:mini + deepseek-coder:1.3b
    elif vram_gb >= 2.0:
        return "lite"       # deepseek-coder:1.3b only
    else:
        return "cloud"      # Groq/OpenAI fallback


MODE_DESCRIPTIONS = {
    "full": "All 4 council models (deepseek + phi3 + llama3.2 + qwen/cyphex-patch)",
    "standard": "2 council models (phi3:mini + deepseek-coder:1.3b)",
    "lite": "1 model only (deepseek-coder:1.3b)",
    "cloud": "Cloud LLM via Groq/OpenAI (set GROQ_API_KEY or OPENAI_API_KEY)",
}

MODE_MODELS = {
    "full": ["deepseek-coder:1.3b", "phi3:mini", "llama3.2:1b", "cyphex-patch"],
    "standard": ["deepseek-coder:1.3b", "phi3:mini"],
    "lite": ["deepseek-coder:1.3b"],
    "cloud": [],
}
