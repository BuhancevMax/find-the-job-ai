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

from App.AI.evaluator import AiEvaluator
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
    Fetch vacancies from a supported platform and evaluate them with AI.
    """

    print(
        f"\n🚀 [START] Платформа: {platform.upper()} | "
        f"Запрос: '{keyword}' | Язык: {language}"
    )

    try:
        scraper = ScraperFactory.get_scraper(platform)
        raw_vacancies = scraper.fetch_jobs(keyword)

        print(f"📦 [INFO] Найдено вакансий: {len(raw_vacancies)}")

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
            language=language,
        )

        print(
            f"🏁 [FINISH] Готово к отправке: "
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
        print(f"❌ [SERVER] {exc}")
        return {
            "status": "error",
            "message": str(exc),
        }
