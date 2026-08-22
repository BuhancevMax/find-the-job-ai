import json
import re
import requests
from bs4 import BeautifulSoup

from App.config import DEFAULT_PAGE_TIMEOUT, SCRAPER_USER_AGENT
from App.models import Vacancy
from App.Scrapers.base import BaseScraper


class DjinniScraper(BaseScraper):
    """Scraper for Djinni."""

    CATEGORY_MAP = {
        # --- .NET / C# ---
        "c#": "dotnet",
        "с#": "dotnet",  # Cyrillic C
        "csharp": "dotnet",
        "c-sharp": "dotnet",
        ".net": "dotnet",
        "dotnet": "dotnet",
        "dot net": "dotnet",
        ".net core": "dotnet",
        ".net framework": "dotnet",
        "asp.net": "dotnet",
        "blazor": "dotnet",
        "wpf": "dotnet",
        "entity framework": "dotnet",
        "c# developer": "dotnet",
        "c# розробник": "dotnet",
        "c# разработчик": "dotnet",
        "c# programmer": "dotnet",
        "c# програміст": "dotnet",
        ".net developer": "dotnet",
        ".net розробник": "dotnet",
        ".net разработчик": "dotnet",
        "dotnet developer": "dotnet",
        "c#/.net": "dotnet",

        # --- Python ---
        "python": "python",
        "py": "python",
        "python3": "python",
        "python developer": "python",
        "python розробник": "python",
        "python разработчик": "python",
        "питон": "python",
        "пайтон": "python",
        "django": "python",
        "flask": "python",
        "fastapi": "python",

        # --- JavaScript / TypeScript / Frontend ---
        "javascript": "javascript",
        "js": "javascript",
        "typescript": "javascript",
        "ts": "javascript",
        "frontend": "frontend",
        "front-end": "frontend",
        "фронтенд": "frontend",
        "фронт-енд": "frontend",
        "react": "react",
        "react.js": "react",
        "reactjs": "react",
        "node": "nodejs",
        "nodejs": "nodejs",
        "node.js": "nodejs",
        "vue": "vuejs",
        "vue.js": "vuejs",
        "vuejs": "vuejs",
        "angular": "angular",
        "angular.js": "angular",
        "svelte": "frontend",
        "next.js": "react",
        "nuxt": "vuejs",
        "html/css": "frontend",
        "web developer": "frontend",
        "веб розробник": "frontend",
        "веб-разработчик": "frontend",

        # --- Java / Kotlin / Android ---
        "java": "java",
        "джава": "java",
        "ява": "java",
        "java developer": "java",
        "spring": "java",
        "spring boot": "java",
        "kotlin": "android",  # Or separate to 'kotlin' depending on your logic
        "android": "android",
        "андроид": "android",
        "андроїд": "android",
        "android developer": "android",

        # --- iOS / Swift / Mobile ---
        "ios": "ios",
        "swift": "ios",
        "objective-c": "ios",
        "apple": "ios",
        "ios developer": "ios",
        "flutter": "mobile_crossplatform",
        "dart": "mobile_crossplatform",
        "react native": "mobile_crossplatform",
        "mobile": "mobile",
        "мобильный разработчик": "mobile",

        # --- Go / Rust / PHP / C++ / Ruby ---
        "golang": "golang",
        "go": "golang",
        "go developer": "golang",
        "rust": "rust",
        "php": "php",
        "пхп": "php",
        "laravel": "php",
        "symfony": "php",
        "c++": "cpp",
        "с++": "cpp",  # Cyrillic C
        "cpp": "cpp",
        "c/c++": "cpp",
        "c": "c",
        "с": "c",      # Cyrillic C
        "ruby": "ruby",
        "ruby on rails": "ruby",
        "ror": "ruby",

        # --- GameDev ---
        "gamedev": "gamedev",
        "геймдев": "gamedev",
        "game developer": "gamedev",
        "разработчик игр": "gamedev",
        "розробник ігор": "gamedev",
        "unity": "unity",
        "unity3d": "unity",
        "unity developer": "unity",
        "unreal engine": "unreal_engine",
        "ue": "unreal_engine",
        "ue4": "unreal_engine",
        "ue5": "unreal_engine",

        # --- QA / Testing ---
        "qa": "qa",
        "qa engineer": "qa",
        "qa manual": "qa",
        "manual qa": "qa",
        "qa automation": "qa_automation",
        "aqa": "qa_automation",
        "auto qa": "qa_automation",
        "тестировщик": "qa",
        "тестувальник": "qa",
        "software tester": "qa",
        "sdet": "qa_automation",
        "qc": "qa",

        # --- DevOps / SysAdmin / Cloud ---
        "devops": "devops",
        "девопс": "devops",
        "devops engineer": "devops",
        "sysadmin": "sysadmin",
        "системный администратор": "sysadmin",
        "системний адміністратор": "sysadmin",
        "сисадмин": "sysadmin",
        "aws": "devops",
        "azure": "devops",
        "gcp": "devops",
        "docker": "devops",
        "kubernetes": "devops",
        "k8s": "devops",
        "site reliability engineer": "devops",
        "sre": "devops",

        # --- Data / Databases ---
        "data science": "data_science",
        "data scientist": "data_science",
        "data engineer": "data_engineer",
        "data analyst": "data_analyst",
        "machine learning": "ml",
        "ml": "ml",
        "ai": "ai",
        "artificial intelligence": "ai",
        "sql": "database",
        "dba": "database",
        "database administrator": "database",
        "базы данных": "database",
        "postgresql": "database",
        "mysql": "database",
        "mongodb": "database",

        # --- Design ---
        "ui/ux": "design",
        "ui ux": "design",
        "ui/ux designer": "design",
        "design": "design",
        "дизайн": "design",
        "дизайнер": "design",
        "web designer": "design",
        "graphic designer": "design",
        "figma": "design",

        # --- Management / Analytics ---
        "project manager": "project_manager",
        "pm": "project_manager",
        "пм": "project_manager",
        "product manager": "product_manager",
        "scrum master": "scrum_master",
        "business analyst": "business_analyst",
        "ba": "business_analyst",
        "бизнес-аналитик": "business_analyst",
        "бізнес-аналітик": "business_analyst",

        # --- HR / Recruiting ---
        "hr": "hr",
        "recruiter": "recruiter",
        "рекрутер": "recruiter",
        "talent acquisition": "recruiter",

        # --- Other / General ---
        "software engineer": "software_engineer",
        "fullstack": "fullstack",
        "full stack": "fullstack",
        "full-stack": "fullstack",
        "программист": "software_engineer",
        "програміст": "software_engineer",
        "developer": "software_engineer"
    }

    @staticmethod
    def _normalize_keyword(keyword: str) -> str:
        """Normalize keyword: fix Cyrillic C#, strip extra spaces."""
        text = keyword.strip().lower()
        # Replace Cyrillic 'с'/'С' with Latin 'c'/'C' near # or ++
        text = re.sub(r'[сС](?=[#\+])', 'c', text)
        return " ".join(text.split())

    def fetch_jobs(self, keyword: str) -> list[Vacancy]:
        clean_key = self._normalize_keyword(keyword)

        # Check if keyword matches a direct category on Djinni
        if clean_key in self.CATEGORY_MAP:
            params = {"primary_keyword": self.CATEGORY_MAP[clean_key]}
        else:
            # Check if any category token is contained in the query
            matched_cat = None
            for key_token, cat_slug in self.CATEGORY_MAP.items():
                if key_token in clean_key:
                    matched_cat = cat_slug
                    break

            if matched_cat:
                params = {"primary_keyword": matched_cat}
            else:
                # Use all_keywords (with underscore) for general full-text search
                params = {"all_keywords": keyword.strip()}

        response = requests.get(
            "https://djinni.co/jobs/",
            headers={"User-Agent": SCRAPER_USER_AGENT},
            params=params,
            timeout=DEFAULT_PAGE_TIMEOUT,
        )

        print(f"[Djinni] URL: {response.url}")
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        jobs_data = []

        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                raw = tag.string or tag.get_text()
                data = json.loads(raw)

                if isinstance(data, list):
                    jobs_data.extend(
                        item
                        for item in data
                        if isinstance(item, dict) and item.get("@type") == "JobPosting"
                    )
                elif isinstance(data, dict) and data.get("@type") == "JobPosting":
                    jobs_data.append(data)
            except (json.JSONDecodeError, TypeError):
                continue

        return self._normalize_data(jobs_data)

    @staticmethod
    def _normalize_data(raw_data: list[dict]) -> list[Vacancy]:
        normalized: list[Vacancy] = []

        for idx, job in enumerate(raw_data):
            exp_data = job.get("experienceRequirements", {})
            months = (
                exp_data.get("monthsOfExperience", 0)
                if isinstance(exp_data, dict)
                else 0
            )

            if months == 0:
                req_exp = "Без опыта"
            elif months < 12:
                req_exp = f"{int(months)} месяцев"
            elif months % 12 == 0:
                req_exp = f"{int(months // 12)} лет/год(а)"
            else:
                req_exp = f"{int(months)} месяцев"

            organization = job.get("hiringOrganization", {})
            company = (
                organization.get("name", "Неизвестно")
                if isinstance(organization, dict)
                else "Неизвестно"
            )

            normalized.append(
                {
                    "_temp_id": idx,
                    "Title": job.get("title", "Без названия"),
                    "Company": company,
                    "Url": job.get("url", ""),
                    "RequiredExperience": req_exp,
                    "DescriptionSnippet": " ".join(
                        str(job.get("description", "")).split()
                    )[:1200],
                }
            )

        return normalized
