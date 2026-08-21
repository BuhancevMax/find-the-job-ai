import json

import requests
from bs4 import BeautifulSoup

from App.config import DEFAULT_PAGE_TIMEOUT, SCRAPER_USER_AGENT
from App.models import Vacancy
from App.Scrapers.base import BaseScraper


class DjinniScraper(BaseScraper):
    """Scraper for Djinni."""

    CATEGORY_MAP = {
        "c#": "dotnet",
        ".net": "dotnet",
        "dotnet": "dotnet",
        "python": "python",
        "py": "python",
        "java": "java",
        "qa": "qa",
        "тестировщик": "qa",
    }

    def fetch_jobs(self, keyword: str) -> list[Vacancy]:
        clean_key = keyword.lower().strip()

        params = (
            {"primary_keyword": self.CATEGORY_MAP[clean_key]}
            if clean_key in self.CATEGORY_MAP
            else {"all-keywords": keyword}
        )

        response = requests.get(
            "https://djinni.co/jobs/",
            headers={"User-Agent": SCRAPER_USER_AGENT},
            params=params,
            timeout=DEFAULT_PAGE_TIMEOUT,
        )

        print(f"🔗 [Djinni] URL: {response.url}")
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
