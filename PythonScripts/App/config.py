import os


# Base URLs for OpenAI-compatible providers
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "groq/compound-mini")
DEFAULT_DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# OpenRouter models ordered by throughput speed (fastest -> slowest).
# Sourced from user's benchmark test (batch=5).
# Model is auto-switched on 429 (rate limit exceeded).
OPENROUTER_MODEL_FALLBACK_CHAIN = [
    "dots-studio/dots-3-note-preview:free",     # 1st: 6.4s
    "poolside/laguna-s-2.1:free",               # 2nd: 13.7s
    "nvidia/nemotron-3-super-120b-a12b:free",   # 3rd: 35.6s
    "stealth/ox-alpha",                         # 4th: 36.0s
    "cohere/north-mini-code:free",              # 5th: 75.4s
]
DEFAULT_OPENROUTER_MODEL = OPENROUTER_MODEL_FALLBACK_CHAIN[0]

# Weights for the final deterministic score.
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
