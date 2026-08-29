import os
import json
import time
import urllib.request


# Base URLs for OpenAI-compatible providers
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
DEFAULT_DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ─────────────────────────────────────────────────────────────────────────────
# OpenRouter fallback chain — verified active free models (fastest/most reliable first)
# Sourced from live OpenRouter API
# ─────────────────────────────────────────────────────────────────────────────
OPENROUTER_MODEL_FALLBACK_CHAIN = [
    "poolside/laguna-s-2.1:free",               # Fast, tested in benchmark (13.7s)
    "google/gemma-4-31b-it:free",               # High quality instruction-following
    "google/gemma-4-26b-a4b-it:free",           # Fast MoE model
    "nvidia/nemotron-3.5-lightning:free",       # High throughput
    "nvidia/nemotron-3-super-120b-a12b:free",   # Stable backup
    "minimax/minimax-m2.7:free",                # Backup
    "cohere/north-mini-code:free",              # Code understanding
    "z-ai/glm-5.2:free",                        # General backup
    "liquid/lfm-2.5-2.6b:free",                 # Lightweight
]
DEFAULT_OPENROUTER_MODEL = OPENROUTER_MODEL_FALLBACK_CHAIN[0]

_cached_free_models: list[str] = []
_last_fetch: float = 0.0


def get_live_openrouter_free_models() -> list[str]:
    """
    Dynamically discover currently active ':free' models from OpenRouter API.
    Caches for 30 minutes, falls back to OPENROUTER_MODEL_FALLBACK_CHAIN on network errors.
    """
    global _cached_free_models, _last_fetch
    now = time.time()
    if _cached_free_models and (now - _last_fetch < 1800):
        return list(_cached_free_models)

    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"User-Agent": "FindTheJobAI/1.0"}
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            models = data.get("data", [])
            live_free = [m["id"] for m in models if ":free" in m.get("id", "")]
            if live_free:
                preferred = [m for m in OPENROUTER_MODEL_FALLBACK_CHAIN if m in live_free]
                others = [m for m in live_free if m not in preferred]
                _cached_free_models = preferred + others
                _last_fetch = now
                return list(_cached_free_models)
    except Exception:
        pass

    return list(OPENROUTER_MODEL_FALLBACK_CHAIN)


# ─────────────────────────────────────────────────────────────────────────────
# Weights for the final deterministic score
# ─────────────────────────────────────────────────────────────────────────────
ROLE_WEIGHT = 0.25
LEVEL_WEIGHT = 0.25
TECH_WEIGHT = 0.30
EXPERIENCE_WEIGHT = 0.20

AI_REQUEST_DELAY_SECONDS = float(os.getenv("AI_REQUEST_DELAY_SECONDS", "0.2"))
DEFAULT_PAGE_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT_SECONDS", "20"))

SUPPORTED_LANGUAGES = {
    "ru": "Russian",
    "uk": "Ukrainian",
    "en": "English",
}

SCRAPER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)

# ─────────────────────────────────────────────────────────────────────────────
# Errors that indicate the model/key is fundamentally broken — skip immediately
# without waiting for retries on the SAME model.
# ─────────────────────────────────────────────────────────────────────────────
FATAL_ERROR_SIGNALS = [
    "invalid_api_key",
    "model not found",
    "model_not_found",
    "no endpoints",
    "404",
    "403",
    "401",
    "connection refused",
    "name or service not known",
    "the model does not exist",
    "this model's maximum context length",
    "is not supported",
    "unavailable",
    "decommissioned",
]
