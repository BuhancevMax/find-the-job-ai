import requests
from bs4 import BeautifulSoup
from App.config import DEFAULT_PAGE_TIMEOUT, SCRAPER_USER_AGENT
from App.models import Vacancy
from App.Scrapers.base import BaseScraper
import datetime

class DouUaScraper(BaseScraper):
    """Scraper for jobs.dou.ua."""

    def fetch_jobs(self, keyword: str) -> list[Vacancy]:
        response = requests.get(
            "https://jobs.dou.ua/vacancies/",
            headers={"User-Agent": SCRAPER_USER_AGENT},
            params={"search": keyword},
            timeout=DEFAULT_PAGE_TIMEOUT,
        )

        print(f"[DOU] URL: {response.url}")
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        jobs: list[Vacancy] = []

        cards = soup.find_all("li", class_="vacancy")
        for idx, card in enumerate(cards):
            try:
                title_elem = card.find("a", class_="vt")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                url = title_elem.get("href")
                if url and not url.startswith("http"):
                    url = "https://jobs.dou.ua" + url

                company_elem = card.find("a", class_="company")
                company = company_elem.get_text(strip=True) if company_elem else "Неизвестно"

                desc_elem = card.find("div", class_="sh-info")
                desc = desc_elem.get_text(strip=True)[:300] + "..." if desc_elem else ""

                salary_elem = card.find("span", class_="salary")
                salary = salary_elem.get_text(strip=True) if salary_elem else ""

                jobs.append({
                    "_temp_id": 0,
                    "Title": title,
                    "Company": company.replace("\xa0", " "),
                    "Url": url or "",
                    "SalaryString": salary,
                    "DescriptionSnippet": desc,
                    "TechStack": "",
                    "AiSummary": "",
                    "AiMatchScore": 0,
                    "RequiredExperience": "",
                })
            except Exception as e:
                print(f"[DOU] Ошибка парсинга карточки: {e}")

        return jobs
