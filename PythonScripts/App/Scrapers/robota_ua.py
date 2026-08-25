import requests
from App.config import DEFAULT_PAGE_TIMEOUT, SCRAPER_USER_AGENT
from App.models import Vacancy
from App.Scrapers.base import BaseScraper
import urllib.parse

class RobotaUaScraper(BaseScraper):
    """Scraper for Robota.ua via their API."""

    def fetch_jobs(self, keyword: str) -> list[Vacancy]:
        # "C#, SQL, .NET" -> "C#" - берём только первое ключевое слово
        primary_keyword = keyword.split(',')[0].strip()

        url = "https://api.rabota.ua/vacancy/search"
        
        response = requests.get(
            url,
            headers={"User-Agent": SCRAPER_USER_AGENT},
            params={"keyWords": primary_keyword, "count": 20},
            timeout=DEFAULT_PAGE_TIMEOUT,
        )

        print(f"[Robota.ua] URL: {response.url}")
        if response.status_code != 200:
            return []

        jobs: list[Vacancy] = []
        
        try:
            data = response.json()
            documents = data.get("documents", [])
            for doc in documents:
                title = doc.get("name", "")
                company = doc.get("companyName", "")
                job_id = doc.get("id", "")
                url = f"https://robota.ua/company0/vacancy{job_id}"
                
                desc = doc.get("shortDescription", "")
                salary = ""
                if doc.get("salary"):
                    salary = f"{doc['salary']} {doc.get('salaryCurrency', '')}"

                jobs.append({
                    "_temp_id": 0,
                    "Title": title,
                    "Company": company,
                    "Url": url,
                    "SalaryString": salary,
                    "DescriptionSnippet": desc[:300],
                    "TechStack": "",
                    "AiSummary": "",
                    "AiMatchScore": 0,
                    "RequiredExperience": "",
                })
        except Exception as e:
            print(f"[Robota.ua] Ошибка парсинга API: {e}")

        return jobs
