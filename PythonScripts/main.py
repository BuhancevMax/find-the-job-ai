import asyncio
import json
import sys
import time

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

from App.AI.evaluator import AiEvaluator, BATCH_SIZE, safe_log
from App.Scrapers import ScraperFactory

MAX_VACANCIES = 14

app = FastAPI(
    title="Job Search AI Backend",
    version="1.0.0",
    description="Job aggregation and AI matching backend.",
)

# Fix #5: specific origins instead of wildcard + credentials (invalid combo per CORS spec)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5104", "https://localhost:5104"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ── Pydantic models for request bodies (Fix #1: api_key out of URL) ──

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


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


# Update legacy GET to POST as well to avoid API key exposure
@app.post("/parse/{platform}")
def parse_jobs(platform: str, body: ParseRequest):
    """Non-streaming endpoint."""
    safe_log(
        f"\n[START] Платформа: {platform.upper()} | "
        f"Запрос: '{body.keyword}' | Язык: {body.language}"
    )

    try:
        scraper = ScraperFactory.get_scraper(platform)
        raw_vacancies = scraper.fetch_jobs(body.keyword)[:MAX_VACANCIES]

        safe_log(f"[INFO] Найдено вакансий: {len(raw_vacancies)}")

        if not raw_vacancies:
            return {
                "status": "success",
                "count": 0,
                "data": [],
                "message": f"По запросу '{body.keyword}' на {platform} ничего не найдено.",
            }

        evaluator = AiEvaluator(api_key=body.api_key)

        from App.models import JobCriteria
        criteria = JobCriteria(
            target_role=body.target_role,
            target_exp=body.target_exp,
            target_stack=body.keyword,
            language=body.language,
        )

        final_vacancies = evaluator.evaluate_vacancies(
            raw_vacancies,
            criteria=criteria,
        )

        safe_log(f"[FINISH] Готово к отправке: {len(final_vacancies)}")

        return {
            "status": "success",
            "count": len(final_vacancies),
            "data": final_vacancies,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:
        safe_log(f"[SERVER ERROR] {exc}")
        return {"status": "error", "message": str(exc)}


# Fix #1: POST body so api_key never appears in URL/logs
@app.post("/parse-stream")
async def parse_jobs_stream(body: ParseRequest):
    """
    Streaming endpoint for multi-platform parsing.
    """
    loop = asyncio.get_running_loop()
    event_queue: asyncio.Queue = asyncio.Queue()

    def push_event(event: dict | None) -> None:
        loop.call_soon_threadsafe(event_queue.put_nowait, event)

    def run_analysis() -> None:
        platforms_str = ", ".join(p.upper() for p in body.platforms)
        safe_log(f"\n[START] Платформы: {platforms_str} | Запрос: '{body.keyword}' | Язык: {body.language}")
        push_event({"type": "progress", "percent": 5, "message": f"Сбор вакансий: {platforms_str}..."})

        try:
            # 1. Сбор со всех платформ
            raw_vacancies = []
            for plat in body.platforms:
                try:
                    scraper = ScraperFactory.get_scraper(plat)
                    jobs = scraper.fetch_jobs(body.keyword)[:MAX_VACANCIES]
                    for j in jobs:
                        j["Source"] = plat
                    raw_vacancies.extend(jobs)
                    safe_log(f"[{plat.upper()}] Найдено: {len(jobs)}")
                except Exception as e:
                    safe_log(f"[{plat.upper()}] Ошибка сбора: {e}")

            # 2. Дедупликация (Компания + Должность)
            unique_jobs = {}
            for vac in raw_vacancies:
                key = f"{vac.get('Company', '')}_{vac.get('Title', '')}".lower().strip()
                if not key:
                    continue
                if key in unique_jobs:
                    # Merge source
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
            push_event({"type": "progress", "percent": 15,
                        "message": f"Найдено {total} уникальных. ИИ-анализ ({total_batches} батч.)..."})

            evaluator = AiEvaluator(api_key=body.api_key)
            
            def on_model_switch(old: str, new: str) -> None:
                safe_log(f"    [MODEL SWITCH] {old} -> {new}")
                push_event({
                    "type": "model_switch", "percent": -1,
                    "message": f"⚠️ Лимит модели «{old}» исчерпан — переключились на «{new}»",
                })

            evaluator.on_model_switch = on_model_switch

            from App.models import JobCriteria
            criteria = JobCriteria(
                target_role=body.target_role,
                target_exp=body.target_exp,
                target_stack=body.keyword,
                language=body.language,
                salary_expectations=body.salary_expectations,
                work_format=body.work_format,
                english_level=body.english_level,
                employment_type=body.employment_type
            )

            evaluated = evaluator.evaluate_vacancies(
                raw_vacancies,
                criteria=criteria,
                on_progress=lambda pct, msg: push_event({"type": "progress", "percent": pct, "message": msg}),
            )

            safe_log(f"[FINISH] Готово к отправке: {len(evaluated)}")
            push_event({"type": "progress", "percent": 97, "message": "Сохранение результатов..."})
            push_event({"type": "complete", "status": "success",
                        "count": len(evaluated), "data": evaluated})

        except Exception as exc:
            safe_log(f"[SERVER ERROR] {exc}")
            push_event({"type": "complete", "status": "error",
                        "message": str(exc), "data": []})
        finally:
            push_event(None)  # sentinel

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
