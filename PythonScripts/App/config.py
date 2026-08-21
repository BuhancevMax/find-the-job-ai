import os


# Base URLs for OpenAI-compatible providers
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "groq/compound-mini")
DEFAULT_DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")

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
