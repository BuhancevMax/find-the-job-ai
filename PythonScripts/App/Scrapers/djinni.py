import json
import requests
from bs4 import BeautifulSoup

from App.config import DEFAULT_PAGE_TIMEOUT, SCRAPER_USER_AGENT
from App.models import Vacancy, JobCriteria
from App.Scrapers.base import BaseScraper
from App.utils import safe_log, clean_tech_token, normalize_experience_text


class DjinniScraper(BaseScraper):
    """Scraper for Djinni with multi-filter and category support."""

    CATEGORY_MAP = {
        # .NET / C#
        "c#": "dotnet",
        "с#": "dotnet",
        "csharp": "dotnet",
        "c-sharp": "dotnet",
        ".net": "dotnet",
        "dotnet": "dotnet",
        "asp.net": "dotnet",
        "blazor": "dotnet",
        "wpf": "dotnet",
        "c#/.net": "dotnet",

        # Python
        "python": "python",
        "py": "python",
        "django": "python",
        "fastapi": "python",

        # JavaScript / Frontend
        "javascript": "javascript",
        "js": "javascript",
        "typescript": "javascript",
        "ts": "javascript",
        "react": "react_native",
        "vue": "javascript",
        "angular": "javascript",
        "frontend": "javascript",

        # Java / Kotlin
        "java": "java",
        "kotlin": "kotlin",
        "android": "android",
        "swift": "ios",
        "ios": "ios",
        "flutter": "flutter",

        # Go / Rust / C++ / PHP
        "go": "golang",
        "golang": "golang",
        "rust": "rust",
        "php": "php",
        "laravel": "php",
        "c++": "cpp",
        "cpp": "cpp",
        "ruby": "ruby",

        # SQL / Data
        "sql": "sql",
        "data engineer": "data_engineer",

        # QA
        "qa": "qa",
        "qa manual": "qa",
        "qa automation": "qa_automation",
        "aqa": "qa_automation",

        # DevOps
        "devops": "devops",
        "docker": "devops",
        "kubernetes": "devops",
        "aws": "devops",
    }

    def _map_experience(self, exp_str: str) -> str | None:
        low = exp_str.lower()
        if "без" in low or "студент" in low or "trainee" in low:
            return "no_exp"
        if "1-3" in low or "1 год" in low or "2 года" in low or "2 роки" in low:
            return "1y"
        if "3-5" in low or "3 года" in low or "4 года" in low:
            return "3y"
        if "5" in low:
            return "5y"
        return None

    def fetch_jobs(self, keyword: str, criteria: JobCriteria | None = None) -> list[Vacancy]:
        raw_stacks = criteria.get_stack_list() if criteria else [s.strip() for s in keyword.split(",") if s.strip()]
        if not raw_stacks and keyword:
            raw_stacks = [keyword.strip()]

        # Determine Djinni primary_keywords
        matched_categories: list[str] = []
        for stack_item in raw_stacks:
            clean = clean_tech_token(stack_item).lower()
            if clean in self.CATEGORY_MAP:
                cat = self.CATEGORY_MAP[clean]
                if cat not in matched_categories:
                    matched_categories.append(cat)
            else:
                for key_token, cat_slug in self.CATEGORY_MAP.items():
                    if key_token in clean and cat_slug not in matched_categories:
                        matched_categories.append(cat_slug)
                        break

        params: dict = {}
        if matched_categories:
            params["primary_keyword"] = matched_categories if len(matched_categories) > 1 else matched_categories[0]
        else:
            params["all_keywords"] = keyword.strip()

        # Add experience and remote parameters
        if criteria:
            exp_code = self._map_experience(criteria.target_exp)
            if exp_code:
                params["exp_level"] = exp_code
            if criteria.is_remote():
                params["employment"] = "remote"

        jobs = self._execute_query(params)

        # Soft fallback: if strict filters returned < 5 jobs, relax exp_level
        if len(jobs) < 5 and "exp_level" in params:
            relaxed_params = dict(params)
            del relaxed_params["exp_level"]
            relaxed_jobs = self._execute_query(relaxed_params)
            existing_urls = {j.get("Url") for j in jobs}
            for rj in relaxed_jobs:
                if rj.get("Url") not in existing_urls:
                    jobs.append(rj)
                    existing_urls.add(rj.get("Url"))

        return jobs

    def _execute_query(self, params: dict) -> list[Vacancy]:
        try:
            response = requests.get(
                "https://djinni.co/jobs/",
                headers={"User-Agent": SCRAPER_USER_AGENT},
                params=params,
                timeout=DEFAULT_PAGE_TIMEOUT,
            )
            safe_log(f"[Djinni] URL: {response.url}")
            if response.status_code != 200:
                return []
        except Exception as e:
            safe_log(f"[Djinni] Ошибка запроса: {e}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        jobs_data = []

        # 1. Parse JSON-LD structured data
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                raw = tag.string or tag.get_text()
                data = json.loads(raw)
                if isinstance(data, list):
                    jobs_data.extend(
                        item for item in data
                        if isinstance(item, dict) and item.get("@type") == "JobPosting"
                    )
                elif isinstance(data, dict) and data.get("@type") == "JobPosting":
                    jobs_data.append(data)
            except (json.JSONDecodeError, TypeError):
                continue

        if jobs_data:
            return self._normalize_json_ld(jobs_data)

        # 2. HTML fallback
        return self._normalize_html_cards(soup)

    @staticmethod
    def _normalize_json_ld(raw_data: list[dict]) -> list[Vacancy]:
        normalized: list[Vacancy] = []
        for idx, job in enumerate(raw_data):
            exp_data = job.get("experienceRequirements", {})
            months = exp_data.get("monthsOfExperience", 0) if isinstance(exp_data, dict) else 0

            if months == 0:
                req_exp = "без опыта"
            elif months < 12:
                req_exp = "до 1 года"
            else:
                years = int(months // 12)
                unit = "год" if (years % 10 == 1 and years % 100 != 11) else "года" if (2 <= years % 10 <= 4 and (years % 100 < 10 or years % 100 >= 20)) else "лет"
                req_exp = f"{years} {unit}"

            org = job.get("hiringOrganization", {})
            company = org.get("name", "Неизвестно") if isinstance(org, dict) else "Неизвестно"

            normalized.append({
                "_temp_id": idx,
                "Title": job.get("title", "Без названия"),
                "Company": company,
                "Url": job.get("url", ""),
                "RequiredExperience": req_exp,
                "DescriptionSnippet": " ".join(str(job.get("description", "")).split())[:1200],
            })
        return normalized

    @staticmethod
    def _normalize_html_cards(soup: BeautifulSoup) -> list[Vacancy]:
        normalized: list[Vacancy] = []
        cards = soup.find_all("li", class_=lambda c: c and "list-jobs__item" in c)
        for idx, card in enumerate(cards):
            title_tag = card.find("a", class_=lambda c: c and "job-list-item__link" in c) or card.find("a", class_="profile")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            url = title_tag.get("href", "")
            if url and not url.startswith("http"):
                url = "https://djinni.co" + url
            company_tag = card.find("a", class_=lambda c: c and "job-list-item__company" in c)
            company = company_tag.get_text(strip=True) if company_tag else "Неизвестно"
            desc_tag = card.find("div", class_=lambda c: c and "job-list-item__description" in c)
            desc = desc_tag.get_text(" ", strip=True) if desc_tag else ""

            normalized.append({
                "_temp_id": idx,
                "Title": title,
                "Company": company,
                "Url": url,
                "RequiredExperience": normalize_experience_text(desc),
                "DescriptionSnippet": desc[:1200],
            })
        return normalized
