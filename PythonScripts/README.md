# AI Job Parser Backend (FastAPI)

Це бекенд-мікросервіс на базі **FastAPI**, що виконує паралельний збір вакансій з провідних майданчиків (**Djinni**, **Work.ua**, **Robota.ua**, **DOU.ua**) та проводить глибокий аналіз вимог за допомогою безкоштовних LLM моделей (**OpenRouter Free Tier**).

## Залежності та Встановлення

Усі необхідні бібліотеки зазначені у `requirements.txt`:
- `fastapi` & `uvicorn` — асинхронний веб-сервер та SSE стрімінг (NDJSON).
- `beautifulsoup4` & `requests` — збір та парсинг HTML/API.
- `cloudscraper` — обхід захисту Cloudflare на платформах пошуку роботи.
- `openai` — взаємодія з каталогом моделей OpenRouter.
- `pydantic` — сувора типізація та валідація даних.

### Як запустити локально

1. Створіть та активуйте віртуальне оточення:
```bash
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate
```

2. Встановіть залежності:
```bash
pip install -r requirements.txt
```

3. Запустіть сервер:
```bash
python -m uvicorn main:app --reload --port 8000
```
