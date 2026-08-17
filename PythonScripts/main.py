from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup
import json
import time
from groq import Groq

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 1. АРХИТЕКТУРА ПАРСЕРОВ (Паттерн Стратегия)
# ==========================================

class BaseScraper(ABC):
    """Абстрактный класс (Интерфейс) для всех будущих парсеров"""
    @abstractmethod
    def fetch_jobs(self, keyword: str) -> list[dict]:
        pass

class DjinniScraper(BaseScraper):
    """Реализация парсера только для Djinni"""

    # Словарь маппинга фильтров. Легко расширяется в одну строку без if/elif!
    CATEGORY_MAP = {
        "c#": "dotnet", ".net": "dotnet", "dotnet": "dotnet",
        "python": "python", "py": "python",
        "java": "java",
        "qa": "qa", "тестировщик": "qa"
    }

    def fetch_jobs(self, keyword: str) -> list[dict]:
        clean_key = keyword.lower().strip()

        # Если слово есть в словаре - берем системный ключ Джинни. Если нет - берем текстовый поиск.
        params = {"primary_keyword": self.CATEGORY_MAP[clean_key]} if clean_key in self.CATEGORY_MAP else {"all-keywords": keyword}

        url = "https://djinni.co/jobs/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

        response = requests.get(url, headers=headers, params=params)
        print(f"🔗 [Парсер Djinni] URL запроса: {response.url}")

        if response.status_code != 200:
            raise Exception(f"Djinni заблокировал запрос. Код: {response.status_code}")

        soup = BeautifulSoup(response.text, 'html.parser')
        jobs_data = []

        for tag in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(tag.string)
                if isinstance(data, list):
                    jobs_data.extend([item for item in data if item.get('@type') == 'JobPosting'])
                elif isinstance(data, dict) and data.get('@type') == 'JobPosting':
                    jobs_data.append(data)
            except:
                continue

        return self._normalize_data(jobs_data)

    def _normalize_data(self, raw_data: list) -> list[dict]:
        """Приводит сырые данные Джинни к единому стандарту для ИИ"""
        normalized = []
        for idx, job in enumerate(raw_data):
            exp_data = job.get("experienceRequirements", {})
            months = exp_data.get("monthsOfExperience", 0) if isinstance(exp_data, dict) else 0

            if months == 0: req_exp = "Без опыта"
            elif months < 12: req_exp = f"{int(months)} месяцев"
            elif months % 12 == 0: req_exp = f"{int(months // 12)} лет/год(а)"
            else: req_exp = f"{int(months)} месяцев"

            normalized.append({
                "_temp_id": idx,
                "Title": job.get("title", "Без названия"),
                "Company": job.get("hiringOrganization", {}).get("name", "Неизвестно"),
                "Url": job.get("url", ""),
                "RequiredExperience": req_exp,
                "DescriptionSnippet": job.get("description", "")[:1200].replace('\n', ' ')
            })
        return normalized

# В будущем ты просто создашь новый класс:
# class WorkUaScraper(BaseScraper): 
#     def fetch_jobs(self, keyword: str): ...

class ScraperFactory:
    """Паттерн Фабрика: решает, какой парсер использовать"""
    @staticmethod
    def get_scraper(platform: str) -> BaseScraper:
        scrapers = {
            "djinni": DjinniScraper(),
            # "workua": WorkUaScraper(), # <-- В будущем просто раскомментируешь это!
        }
        platform_key = platform.lower()
        if platform_key not in scrapers:
            raise ValueError(f"Платформа '{platform}' пока не поддерживается нашей системой.")
        return scrapers[platform_key]

# ==========================================
# 2. УНИВЕРСАЛЬНЫЙ АНАЛИЗАТОР ИИ
# ==========================================

class AiEvaluator:
    """Этот класс принимает стандартизированные данные с ЛЮБОГО сайта и оценивает их"""
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)

    def evaluate_vacancies(self, vacancies: list[dict], target_role: str, target_exp: str) -> list[dict]:
        if not vacancies:
            return []

        evaluated_vacancies = []
        batch_size = 5

        for i in range(0, len(vacancies), batch_size):
            batch = vacancies[i:i+batch_size]

            prompt = f"""
            Ты строгий IT HR-аналитик. Оцени релевантность вакансий для кандидата.
            ПРОФИЛЬ КАНДИДАТА: Должность: {target_role}, Опыт: {target_exp}
            
            ИНСТРУКЦИЯ (AiMatchScore 0-100):
            1. Стек совершенно не совпадает = 0-20.
            2. Вакансия Middle/Senior, а кандидат Junior/Trainee (Без опыта) = 0-30.
            3. Идеальное совпадение стека и уровня = 80-100.
            
            Верни JSON: {{ "results": [ {{"temp_id": <id>, "TechStack": "<стек>", "AiSummary": "<суть в 1 предложении на русском>", "AiMatchScore": <0-100>}} ] }}
            
            ВАКАНСИИ:
            """
            for vac in batch:
                prompt += f"\ntemp_id: {vac['_temp_id']}\nНазвание: {vac['Title']}\nТребуемый опыт: {vac['RequiredExperience']}\nОписание: {vac['DescriptionSnippet']}\n"

            print(f"🧠 [ИИ] Анализируем батч {i//batch_size + 1}...")

            try:
                response = self.client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="openai/gpt-oss-20b",
                    response_format={"type": "json_object"},
                    temperature=0.1
                )

                ai_results = json.loads(response.choices[0].message.content).get("results", [])

                for ai_info in ai_results:
                    matched = next((v for v in batch if v["_temp_id"] == ai_info.get("temp_id")), None)
                    if matched:
                        matched["TechStack"] = str(ai_info.get("TechStack", ""))
                        matched["AiSummary"] = str(ai_info.get("AiSummary", ""))
                        matched["AiMatchScore"] = int(ai_info.get("AiMatchScore", 0))

            except Exception as e:
                print(f"❌ Ошибка ИИ: {e}")

            # Очищаем системные поля перед отправкой на фронт
            for v in batch:
                if "_temp_id" in v: del v["_temp_id"]
                if "DescriptionSnippet" in v: del v["DescriptionSnippet"]
                # Заполняем дефолтными значениями, если ИИ упал
                if "TechStack" not in v:
                    v["TechStack"] = "Ошибка анализа"
                    v["AiSummary"] = "Не удалось проанализировать"
                    v["AiMatchScore"] = 0
                evaluated_vacancies.append(v)

            time.sleep(1.5)

        return evaluated_vacancies

# ==========================================
# 3. ЕДИНАЯ ТОЧКА ВХОДА (Универсальный Endpoint)
# ==========================================

# Обрати внимание: теперь URL динамический /parse/{platform}
@app.get("/parse/{platform}")
def parse_jobs(platform: str, api_key: str, keyword: str, target_role: str, target_exp: str):
    print(f"\n🚀 [START] Сбор для платформы: {platform.upper()} | Запрос: '{keyword}'")

    try:
        # 1. Запрашиваем парсер для указанного сайта у Фабрики
        scraper = ScraperFactory.get_scraper(platform)

        # 2. Собираем сырые данные
        raw_vacancies = scraper.fetch_jobs(keyword)
        print(f"📦 [INFO] Найдено {len(raw_vacancies)} вакансий.")

        if not raw_vacancies:
            return {"status": "error", "message": f"По запросу '{keyword}' на {platform} ничего не найдено."}

        # 3. Отдаем сырые данные ИИ-анализатору
        evaluator = AiEvaluator(api_key=api_key)
        final_vacancies = evaluator.evaluate_vacancies(raw_vacancies, target_role, target_exp)

        print(f"🏁 [FINISH] Готово к отправке: {len(final_vacancies)}")
        return {"status": "success", "count": len(final_vacancies), "data": final_vacancies}

    except ValueError as ve:
        # Срабатывает, если передали неизвестную платформу
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        return {"status": "error", "message": str(e)}