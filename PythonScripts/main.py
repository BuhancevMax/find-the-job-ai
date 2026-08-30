import asyncio
import json
import sys

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from App.AI.evaluator import AiEvaluator, BATCH_SIZE
from App.AI.chat_service import VacancyChatService
from App.models import JobCriteria
from App.Scrapers import ScraperFactory
from App.utils import safe_log

MAX_VACANCIES = 14

app = FastAPI(
    title="Job Search AI Backend",
    version="1.0.0",
    description="Job aggregation and AI matching backend.",
)

# CORS configuration allowing local Blazor development ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5104",
        "https://localhost:5104",
        "http://localhost:7123",
        "https://localhost:7123",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ParseRequest(BaseModel):
    api_key: str
    keyword: str
    target_role: str
    target_exp: str
    language: str
    platforms: list[str]
    salary_expectations: str = ""
    work_format: str = ""
    english_level: str = ""
    employment_type: str = ""


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    api_key: str
    vacancy: dict
    history: list[ChatMessage] = []
    message: str


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/chat")
def chat_with_vacancy(body: ChatRequest):
    """
    Secure, vacancy-scoped AI chat endpoint.
    Applies dual-layer security: system prompt + input/output scanning.
    """
    if not body.api_key or len(body.api_key) < 10:
        raise HTTPException(status_code=400, detail="Invalid API key.")
    if not body.message or len(body.message.strip()) == 0:
        raise HTTPException(status_code=400, detail="Empty message.")
    if len(body.message) > 600:
        raise HTTPException(status_code=400, detail="Message too long (max 600 chars).")

    try:
        service = VacancyChatService(api_key=body.api_key, vacancy=body.vacancy)
        history = [{"role": m.role, "content": m.content} for m in body.history]
        reply = service.chat(history=history, user_message=body.message)
        return {"reply": reply}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        safe_log(f"[CHAT ERROR] {exc}")
        return {"reply": "Произошла ошибка при обращении к ИИ. Пожалуйста, попробуйте ещё раз."}


@app.post("/parse-stream")
async def parse_jobs_stream(body: ParseRequest):
    """
    Streaming endpoint for multi-platform job aggregation and AI matching.
    """
    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue = asyncio.Queue()

    def push_event(event: dict | None) -> None:
        loop.call_soon_threadsafe(event_queue.put_nowait, event)

    def run_analysis() -> None:
        platforms_str = ", ".join(p.upper() for p in body.platforms)
        safe_log(f"\n[START] Платформы: {platforms_str} | Запрос: '{body.keyword}' | Язык: {body.language}")
        push_event({"type": "progress", "percent": 5, "message": f"Сбор вакансий: {platforms_str}..."})

        criteria = JobCriteria(
            target_role=body.target_role,
            target_exp=body.target_exp,
            target_stack=body.keyword,
            language=body.language,
            salary_expectations=body.salary_expectations,
            work_format=body.work_format,
            english_level=body.english_level,
            employment_type=body.employment_type,
            stacks=[s.strip() for s in body.keyword.split(",") if s.strip()],
        )

        try:
            # 1. Aggregate across selected platforms
            raw_vacancies = []
            for plat in body.platforms:
                try:
                    scraper = ScraperFactory.get_scraper(plat)
                    jobs = scraper.fetch_jobs(body.keyword, criteria=criteria)[:MAX_VACANCIES]
                    for j in jobs:
                        j["Source"] = plat
                    raw_vacancies.extend(jobs)
                    safe_log(f"[{plat.upper()}] Найдено: {len(jobs)}")
                except Exception as e:
                    safe_log(f"[{plat.upper()}] Ошибка сбора: {e}")

            # 2. Deduplicate by Company + Title
            unique_jobs = {}
            for vac in raw_vacancies:
                key = f"{vac.get('Company', '')}_{vac.get('Title', '')}".lower().strip()
                if not key:
                    continue
                if key in unique_jobs:
                    existing_sources = unique_jobs[key].get("Source", "")
                    new_source = vac.get("Source", "")
                    if new_source not in existing_sources:
                        unique_jobs[key]["Source"] = f"{existing_sources}, {new_source}"
                else:
                    unique_jobs[key] = vac

            raw_vacancies = list(unique_jobs.values())
            total = len(raw_vacancies)
            safe_log(f"[INFO] После дедупликации: {total} уникальных")

            if total == 0:
                safe_log("[FINISH] Вакансий не найдено.")
                push_event({
                    "type": "complete", "status": "success", "count": 0,
                    "data": [], "message": f"По запросу '{body.keyword}' ничего не найдено.",
                })
                return

            total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
            push_event({
                "type": "progress", "percent": 15,
                "message": f"Найдено {total} уникальных. ИИ-анализ ({total_batches} батч.)...",
            })

            evaluator = AiEvaluator(api_key=body.api_key)

            def on_model_switch(old: str, new: str) -> None:
                safe_log(f"    [MODEL SWITCH] {old} -> {new}")
                push_event({
                    "type": "model_switch", "percent": -1,
                    "message": f"⚠ Лимит модели «{old}» исчерпан — переключились на «{new}»",
                })

            evaluator.on_model_switch = on_model_switch

            evaluated = evaluator.evaluate_vacancies(
                raw_vacancies,
                criteria=criteria,
                on_progress=lambda pct, msg: push_event({"type": "progress", "percent": pct, "message": msg}),
            )

            safe_log(f"[FINISH] Готово к отправке: {len(evaluated)}")
            push_event({"type": "progress", "percent": 97, "message": "Сохранение результатов..."})
            push_event({
                "type": "complete", "status": "success",
                "count": len(evaluated), "data": evaluated,
            })

        except Exception as exc:
            safe_log(f"[SERVER ERROR] {exc}")
            push_event({
                "type": "complete", "status": "error",
                "message": str(exc), "data": [],
            })
        finally:
            push_event(None)

    async def generate_events():
        analysis_task = asyncio.create_task(asyncio.to_thread(run_analysis))
        try:
            while True:
                event = await event_queue.get()
                if event is None:
                    break
                yield json.dumps(event, ensure_ascii=False) + "\n"
        finally:
            try:
                await analysis_task
            except Exception:
                pass

    return StreamingResponse(generate_events(), media_type="application/x-ndjson")
