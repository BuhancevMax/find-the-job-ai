import re
import requests
from bs4 import BeautifulSoup

from App.config import DEFAULT_PAGE_TIMEOUT, SCRAPER_USER_AGENT
from App.models import Vacancy
from App.Scrapers.base import BaseScraper


class WorkUaScraper(BaseScraper):
    """Scraper for Work.ua."""

    @staticmethod
    def _normalize_keyword(keyword: str) -> str:
        """Normalize keyword: fix Cyrillic C#, strip extra spaces."""
        text = keyword.strip()
        # Replace Cyrillic 'с'/'С' with Latin 'c'/'C' near # or ++
        text = re.sub(r'[сС](?=[#\+])', 'C', text)
        return " ".join(text.split())

    def fetch_jobs(self, keyword: str) -> list[Vacancy]:
        clean_key = self._normalize_keyword(keyword)

        response = requests.get(
            "https://www.work.ua/jobs/",
            headers={
                "User-Agent": SCRAPER_USER_AGENT,
                "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8",
            },
            params={"search": clean_key},
            timeout=DEFAULT_PAGE_TIMEOUT,
        )

        print(f"[Work.ua] URL: {response.url}")
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        jobs: list[Vacancy] = []

        cards = soup.find_all(
            "div",
            class_=lambda classes: classes and "card-hover" in classes,
        )

        for idx, card in enumerate(cards):
            try:
                title_anchor = card.find("h2").find("a")
                if not title_anchor:
                    continue

                href = title_anchor.get("href", "")
                if not href:
                    continue

                title = title_anchor.get_text(" ", strip=True)
                link = (
                    href
                    if href.startswith("http")
                    else f"https://www.work.ua{href}"
                )

                desc_tag = card.find("p")
                description = (
                    desc_tag.get_text(" ", strip=True) if desc_tag else ""
                )

                company = "Неизвестно"
                company_element = (
                    card.find("span", class_="strong-600") or card.find("b")
                )
                if company_element:
                    company = company_element.get_text(" ", strip=True)

                jobs.append(
                    {
                        "_temp_id": idx,
                        "Title": title,
                        "Company": company,
                        "Url": link,
                        "RequiredExperience": "Смотреть в описании",
                        "DescriptionSnippet": description[:1200],
                    }
                )
            except (AttributeError, TypeError, KeyError):
                continue

        return jobs
