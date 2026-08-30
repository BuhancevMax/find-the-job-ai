import json
import os
import time
import urllib.request


# Base URL for OpenRouter
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ─────────────────────────────────────────────────────────────────────────────
# OpenRouter fallback chain — verified active free models (fastest & most reliable first)
# ─────────────────────────────────────────────────────────────────────────────
OPENROUTER_MODEL_FALLBACK_CHAIN = [
    "minimax/minimax-m3:free",                                # 2-6s (Fastest & Accurate JSON)
    "dots-studio/dots-3-note-preview:free",                   # ~8s
    "inclusionai/ling-3.0-flash-fin:free",                    # ~8.9s
    "cohere/north-mini-code:free",                            # ~10.6s
    "minimax/minimax-m2.7:free",                              # ~11.5s
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",     # ~12.7s
    "poolside/laguna-s-2.1:free",                             # ~9.7s
    "openrouter/free",                                        # Native OpenRouter Free Router
]
DEFAULT_OPENROUTER_MODEL = OPENROUTER_MODEL_FALLBACK_CHAIN[0]

_cached_free_models: list[str] = []
_last_fetch: float = 0.0


def get_live_openrouter_free_models() -> list[str]:
    """
    Dynamically discover currently active ':free' models from OpenRouter API.
    Caches for 30 minutes, falls back to OPENROUTER_MODEL_FALLBACK_CHAIN on network errors/timeouts.
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
        with urllib.request.urlopen(req, timeout=2.0) as resp:
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
# Weights for the deterministic evaluation score
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
# Fatal errors indicating the model/key is broken — fail fast to next fallback model
# ─────────────────────────────────────────────────────────────────────────────
FATAL_ERROR_SIGNALS = [
    "invalid_api_key",
    "model not found",
    "model_not_found",
    "no endpoints",
    "404",
    "403",
    "401",
    "400",
    "bad request",
    "must have 3 items",
    "connection refused",
    "name or service not known",
    "the model does not exist",
    "this model's maximum context length",
    "is not supported",
    "unavailable",
    "decommissioned",
]
