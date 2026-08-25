# AI Job Parser Backend (FastAPI)

Это микросервис на базе FastAPI, который выполняет парсинг вакансий с популярных площадок (Djinni, Work.ua, Robota.ua, DOU) и оценивает их через AI (OpenRouter, Groq, DeepSeek).

## Зависимости и Установка

Все необходимые библиотеки перечислены в `requirements.txt`.
Проект использует:
- `fastapi` & `uvicorn` — для веб-сервера.
- `beautifulsoup4` & `requests` — для базового парсинга и взаимодействия с API.
- `cloudscraper` — для обхода защиты Cloudflare (например, на Work.ua).
- `openai` — для работы с LLM провайдерами через OpenAI-совместимое API.

### Как запустить локально

1. Создайте и активируйте виртуальное окружение:
```bash
python -m venv .venv
# На Windows:
.venv\Scripts\activate
# На Mac/Linux:
source .venv/bin/activate
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. (Опционально) Настройте переменные окружения:
Скопируйте `.env.example` в `.env` и укажите нужные ключи или настройки.

4. Запустите сервер:
```bash
uvicorn main:app --reload --port 8000
```
