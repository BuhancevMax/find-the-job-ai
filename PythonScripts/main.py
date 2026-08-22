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

from App.AI.evaluator import AiEvaluator, BATCH_SIZE, safe_log
from App.AI.prompt_loader import load_prompt
from App.Scrapers import ScraperFactory


app = FastAPI(
    title="Job Search AI Backend",
    version="1.0.0",
    description="Job aggregation and AI matching backend.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/parse/{platform}")
def parse_jobs(
    platform: str,
    api_key: str,
    keyword: str,
    target_role: str,
    target_exp: str,
    language: str,
):
    """
    Fetch vacancies from a supported platform and evaluate them with AI (standard non-streaming).
    """

    safe_log(
        f"\n[START] Платформа: {platform.upper()} | "
        f"Запрос: '{keyword}' | Язык: {language}"
    )

    try:
        scraper = ScraperFactory.get_scraper(platform)
        raw_vacancies = scraper.fetch_jobs(keyword)

        safe_log(f"[INFO] Найдено вакансий: {len(raw_vacancies)}")

        if not raw_vacancies:
            return {
                "status": "success",
                "count": 0,
                "data": [],
                "message": (
                    f"По запросу '{keyword}' на {platform} "
                    "ничего не найдено."
                ),
            }

        evaluator = AiEvaluator(api_key=api_key)

        final_vacancies = evaluator.evaluate_vacancies(
            raw_vacancies,
            target_role=target_role,
            target_exp=target_exp,
            target_stack=keyword,
            language=language,
        )

        safe_log(
            f"[FINISH] Готово к отправке: "
            f"{len(final_vacancies)}"
        )

        return {
            "status": "success",
            "count": len(final_vacancies),
            "data": final_vacancies,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:
        safe_log(f"[SERVER ERROR] {exc}")
        return {
            "status": "error",
            "message": str(exc),
        }


@app.get("/parse-stream/{platform}")
async def parse_jobs_stream(
    platform: str,
    api_key: str,
    keyword: str,
    target_role: str,
    target_exp: str,
    language: str,
):

    # Shared event queue between the sync AI thread and this async generator
    event_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def push_event(event: dict):
        """Thread-safe: put event onto the asyncio queue from a sync thread."""
        loop.call_soon_threadsafe(event_queue.put_nowait, event)

    def run_analysis():
        """
        Runs in a separate thread (via asyncio.to_thread).
        Pushes events to the queue so the async generator can yield them.
        """
        safe_log(f"\n[START] Платформа: {platform.upper()} | Запрос: '{keyword}' | Язык: {language}")

        push_event({"type": "progress", "percent": 5,
                    "message": f"Поиск и сбор вакансий на {platform.upper()}..."})

        try:
            scraper = ScraperFactory.get_scraper(platform)
            raw_vacancies = scraper.fetch_jobs(keyword)
            
            # Limit to 14 vacancies maximum
            if len(raw_vacancies) > 14:
                raw_vacancies = raw_vacancies[:14]

            total = len(raw_vacancies)
            safe_log(f"[INFO] Найдено вакансий: {total}")

            if total == 0:
                safe_log("[FINISH] Вакансий не найдено.")
                push_event({"type": "complete", "status": "success", "count": 0,
                            "data": [], "message": f"По запросу '{keyword}' на {platform} ничего не найдено."})
                return

            total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

            push_event({"type": "progress", "percent": 15,
                        "message": f"Найдено {total} вакансий. Запускаем ИИ-анализ ({total_batches} батч.)..."})

            evaluator = AiEvaluator(api_key=api_key)
            safe_log(f"[AI] Анализируем {total} вакансий через {evaluator.provider} ({evaluator.model})...")

            # Hook for model switch notifications
            def on_model_switch(old_model: str, new_model: str):
                safe_log(f"    [MODEL SWITCH] {old_model} -> {new_model}")
                push_event({
                    "type": "model_switch",
                    "percent": -1,  # sentinel: don't update bar
                    "message": f"⚠️ Лимит модели «{old_model}» исчерпан — переключились на «{new_model}»"
                })

            evaluator.on_model_switch = on_model_switch

            evaluated_vacancies = []

            for start in range(0, total, BATCH_SIZE):
                batch = raw_vacancies[start: start + BATCH_SIZE]
                batch_num = start // BATCH_SIZE + 1

                for idx, vac in enumerate(batch):
                    vac["_temp_id"] = start + idx

                vacancies_text = evaluator._build_batch_text(batch)
                prompt = load_prompt(
                    target_role=target_role,
                    target_exp=target_exp,
                    target_stack=keyword,
                    language=language,
                    vacancies_text=vacancies_text,
                )

                # Progress at start of batch
                pct_start = 15 + int(((batch_num - 1) / total_batches) * 75)
                push_event({"type": "progress", "percent": pct_start,
                            "message": f"ИИ анализирует батч {batch_num}/{total_batches} (вакансии {start + 1}–{min(start + len(batch), total)})..."})

                # --- Run AI call in a sub-thread so we can tick progress ---
                import threading
                ai_result_holder: list = []
                ai_error_holder: list = []

                def do_ai_call():
                    try:
                        result = evaluator._request_ai_with_retry(prompt)
                        ai_result_holder.append(result)
                    except Exception as e:
                        ai_error_holder.append(e)

                ai_thread = threading.Thread(target=do_ai_call, daemon=True)
                ai_thread.start()

                # Send intermediate progress ticks while AI is working
                t0 = time.time()
                pct_end = 15 + int((batch_num / total_batches) * 75)
                tick_interval = 2.0  # seconds between ticks
                while ai_thread.is_alive():
                    ai_thread.join(timeout=tick_interval)
                    if ai_thread.is_alive():
                        # Smoothly crawl toward pct_end, but cap at pct_end - 2
                        elapsed = time.time() - t0
                        # Estimate: each batch takes ~10-20s → use time fraction
                        estimated_time = 15.0
                        frac = min(elapsed / estimated_time, 0.90)
                        tick_pct = int(pct_start + frac * (pct_end - pct_start))
                        tick_pct = min(tick_pct, pct_end - 1)  # never reach pct_end
                        push_event({"type": "progress", "percent": tick_pct,
                                    "message": f"ИИ думает... батч {batch_num}/{total_batches}"})

                elapsed_total = time.time() - t0

                if ai_error_holder:
                    safe_log(f"  [ERROR] Сбой батча {batch_num}: {ai_error_holder[0]}")
                    evaluated_vacancies.extend([evaluator._fallback_vacancy(v) for v in batch])
                else:
                    ai_results = ai_result_holder[0] if ai_result_holder else []
                    merged = evaluator._merge_results(batch, ai_results)
                    evaluated_vacancies.extend(merged)
                    safe_log(f"  [AI] Батч {batch_num}/{total_batches} готов за {elapsed_total:.2f}с (распознано {len(ai_results)}/{len(batch)})")

                # Progress at end of batch (confirmed)
                push_event({"type": "progress", "percent": pct_end,
                            "message": f"Батч {batch_num}/{total_batches} готов — проанализировано {len(evaluated_vacancies)}/{total}"})

                if start + BATCH_SIZE < total:
                    time.sleep(1.0)

            safe_log(f"[FINISH] Готово к отправке: {len(evaluated_vacancies)}")

            push_event({"type": "progress", "percent": 97,
                        "message": "Сохранение результатов..."})

            push_event({"type": "complete", "status": "success",
                        "count": len(evaluated_vacancies), "data": evaluated_vacancies})

        except Exception as exc:
            safe_log(f"[SERVER ERROR] {exc}")
            push_event({"type": "complete", "status": "error",
                        "message": str(exc), "data": []})

        finally:
            # Sentinel: signal that the thread is done
            push_event(None)

    async def generate_events():
        # Start analysis in a background thread
        analysis_task = asyncio.create_task(asyncio.to_thread(run_analysis))

        try:
            while True:
                event = await event_queue.get()
                if event is None:
                    # Sentinel: analysis complete
                    break
                yield json.dumps(event, ensure_ascii=False) + "\n"
        finally:
            # Make sure background task is awaited
            try:
                await analysis_task
            except Exception:
                pass

    return StreamingResponse(generate_events(), media_type="application/x-ndjson")
