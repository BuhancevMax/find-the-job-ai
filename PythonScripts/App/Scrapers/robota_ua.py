from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup

from App.config import DEFAULT_PAGE_TIMEOUT, SCRAPER_USER_AGENT
from App.models import Vacancy, JobCriteria
from App.Scrapers.base import BaseScraper
from App.utils import safe_log, clean_tech_token, normalize_experience_text


def _fetch_single_robota_details(vac_id: str) -> tuple[list[str], str, str]:
    """Fetch full description, search tags, and experience from Robota.ua API."""
    if not vac_id:
        return [], "", ""
    try:
        r = requests.get(f"https://api.rabota.ua/vacancy?id={vac_id}", headers={"User-Agent": SCRAPER_USER_AGENT}, timeout=5)
        if r.status_code != 200:
            return [], "", ""
        data = r.json()
        tags = [t.get("name", "") for t in data.get("searchTags", []) if isinstance(t, dict) and t.get("name")]
        raw_desc = data.get("description", "") or ""
        soup = BeautifulSoup(raw_desc, "html.parser")
        desc = soup.get_text(" ", strip=True)
        exp = normalize_experience_text(desc)
        return tags, desc, exp
    except Exception:
        return [], "", ""


class RobotaUaScraper(BaseScraper):
    """Scraper for Robota.ua via their public search API with details enrichment."""

    def _map_experience(self, exp_str: str) -> int | None:
        low = exp_str.lower()
        if "без" in low or "студент" in low or "trainee" in low:
            return 1  # Без досвіду
        if "1-3" in low or "1 год" in low or "2 года" in low or "2 роки" in low:
            return 2  # Від 1 до 2 років
        if "3-5" in low or "3 года" in low or "4 года" in low:
            return 3  # Від 2 до 5 років
        if "5" in low:
            return 4  # Більше 5 років
        return None

    def fetch_jobs(self, keyword: str, criteria: JobCriteria | None = None) -> list[Vacancy]:
        raw_stacks = criteria.get_stack_list() if criteria else [s.strip() for s in keyword.split(",") if s.strip()]
        if not raw_stacks and keyword:
            raw_stacks = [keyword.strip()]

        cleaned_tokens = [clean_tech_token(s) for s in raw_stacks if s]
        search_query = " ".join(cleaned_tokens[:3]) if cleaned_tokens else keyword.strip()

        params: dict = {
            "keyWords": search_query,
            "count": 20,
        }

        if criteria:
            exp_id = self._map_experience(criteria.target_exp)
            if exp_id:
                params["experienceId"] = exp_id
            if criteria.is_remote():
                params["scheduleId"] = 3  # Дистанційна робота

        jobs = self._execute_query(params)

        # Soft fallback: if strict query returned < 5 jobs, remove experienceId & scheduleId
        if len(jobs) < 5 and ("experienceId" in params or "scheduleId" in params):
            relaxed_params = {
                "keyWords": search_query,
                "count": 20,
            }
            relaxed_jobs = self._execute_query(relaxed_params)
            existing_urls = {j.get("Url") for j in jobs}
            for rj in relaxed_jobs:
                if rj.get("Url") not in existing_urls:
                    jobs.append(rj)
                    existing_urls.add(rj.get("Url"))

        if jobs:
            self._enrich_jobs_details(jobs)

        return jobs

    def _enrich_jobs_details(self, jobs: list[Vacancy]) -> None:
        raw_ids = [j.get("_raw_id", "") for j in jobs]
        if not any(raw_ids):
            return

        with ThreadPoolExecutor(max_workers=min(6, len(jobs))) as executor:
            details_list = list(executor.map(_fetch_single_robota_details, raw_ids))

        for vac, (tags, full_desc, exp) in zip(jobs, details_list):
            if tags:
                vac["TechStack"] = ", ".join(tags)
            if full_desc:
                vac["DescriptionSnippet"] = full_desc[:1500]
            if exp and exp != "в описании":
                vac["RequiredExperience"] = exp
            vac.pop("_raw_id", None)

    def _execute_query(self, params: dict) -> list[Vacancy]:
        url = "https://api.rabota.ua/vacancy/search"
        try:
            response = requests.get(
                url,
                headers={"User-Agent": SCRAPER_USER_AGENT},
                params=params,
                timeout=DEFAULT_PAGE_TIMEOUT,
            )
            safe_log(f"[Robota.ua] URL: {response.url}")
            if response.status_code != 200:
                return []
            data = response.json()
        except Exception as e:
            safe_log(f"[Robota.ua] Ошибка API: {e}")
            return []

        jobs: list[Vacancy] = []
        documents = data.get("documents", [])
        for idx, doc in enumerate(documents):
            title = doc.get("name", "")
            company = doc.get("companyName", "Неизвестно")
            job_id = str(doc.get("id", ""))
            vac_url = f"https://robota.ua/company0/vacancy{job_id}" if job_id else ""

            desc = doc.get("shortDescription", "")
            salary = ""
            if doc.get("salary"):
                salary = f"{doc['salary']} {doc.get('salaryCurrency', '')}"

            card_exp = normalize_experience_text(desc)

            jobs.append({
                "_temp_id": idx,
                "_raw_id": job_id,
                "Title": title,
                "Company": company,
                "Url": vac_url,
                "SalaryString": salary,
                "DescriptionSnippet": desc[:1200],
                "TechStack": "",
                "AiSummary": "",
                "AiMatchScore": 0,
                "RequiredExperience": card_exp,
            })

        return jobs
