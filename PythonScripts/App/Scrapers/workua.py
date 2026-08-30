from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
import cloudscraper

from App.config import DEFAULT_PAGE_TIMEOUT
from App.models import Vacancy, JobCriteria
from App.Scrapers.base import BaseScraper
from App.utils import safe_log, clean_tech_token, normalize_experience_text


def _fetch_single_workua_details(scraper: cloudscraper.CloudScraper, url: str) -> tuple[list[str], str, str]:
    """Fetch skills, full description and conditions from individual Work.ua page."""
    if not url:
        return [], "", ""
    try:
        r = scraper.get(url, timeout=7)
        if r.status_code != 200:
            return [], "", ""
        soup = BeautifulSoup(r.text, "html.parser")
        skills = [li.get_text(strip=True) for li in soup.find_all("li", class_=lambda c: c and "label-skill" in c)]
        desc_div = soup.find("div", id="job-description")
        desc = desc_div.get_text(" ", strip=True) if desc_div else ""
        cond_elem = soup.find(lambda tag: tag.name in ["p", "div"] and tag.find("span", title="Умови й вимоги"))
        cond_text = cond_elem.get_text(" ", strip=True) if cond_elem else ""
        return skills, desc, cond_text
    except Exception:
        return [], "", ""


class WorkUaScraper(BaseScraper):
    """Scraper for Work.ua with multi-filter, rich details enrichment, and fallback support."""

    def _map_experience(self, exp_str: str) -> str | None:
        low = exp_str.lower()
        if "без" in low or "студент" in low or "trainee" in low:
            return "0"
        if "1-3" in low or "1 год" in low or "2 года" in low or "2 роки" in low:
            return "1"
        if "3-5" in low or "3 года" in low or "4 года" in low:
            return "2"
        if "5" in low:
            return "3"
        return None

    def fetch_jobs(self, keyword: str, criteria: JobCriteria | None = None) -> list[Vacancy]:
        raw_stacks = criteria.get_stack_list() if criteria else [s.strip() for s in keyword.split(",") if s.strip()]
        if not raw_stacks and keyword:
            raw_stacks = [keyword.strip()]

        cleaned_tokens = [clean_tech_token(s) for s in raw_stacks if s]
        search_query = " ".join(cleaned_tokens[:2]) if len(cleaned_tokens) > 1 else (cleaned_tokens[0] if cleaned_tokens else keyword.strip())

        params: dict = {"search": search_query}

        if criteria:
            exp_code = self._map_experience(criteria.target_exp)
            if exp_code:
                params["experience"] = exp_code
            if criteria.is_remote():
                params["remote"] = "1"

        jobs = self._execute_query(params)

        # Soft fallback: if strict query returned < 5 jobs, relax experience & remote or try single primary token
        if len(jobs) < 5:
            if "experience" in params or "remote" in params:
                relaxed_jobs = self._execute_query({"search": search_query})
                existing_urls = {j.get("Url") for j in jobs}
                for rj in relaxed_jobs:
                    if rj.get("Url") not in existing_urls:
                        jobs.append(rj)
                        existing_urls.add(rj.get("Url"))

            if len(jobs) < 5 and cleaned_tokens:
                single_token = cleaned_tokens[0]
                if single_token != search_query:
                    single_jobs = self._execute_query({"search": single_token})
                    existing_urls = {j.get("Url") for j in jobs}
                    for rj in single_jobs:
                        if rj.get("Url") not in existing_urls:
                            jobs.append(rj)
                            existing_urls.add(rj.get("Url"))

        # Enrich jobs with skills, full description, and experience from individual pages
        if jobs:
            self._enrich_jobs_details(jobs)

        return jobs

    def _enrich_jobs_details(self, jobs: list[Vacancy]) -> None:
        urls = [j.get("Url", "") for j in jobs]
        if not any(urls):
            return

        scraper = cloudscraper.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "desktop": True,
            }
        )

        with ThreadPoolExecutor(max_workers=min(6, len(jobs))) as executor:
            details_list = list(executor.map(lambda u: _fetch_single_workua_details(scraper, u), urls))

        for vac, (skills, full_desc, cond_text) in zip(jobs, details_list):
            if skills:
                vac["TechStack"] = ", ".join(skills)
            if full_desc:
                vac["DescriptionSnippet"] = full_desc[:1500]

            exp = normalize_experience_text(cond_text or full_desc or vac.get("RequiredExperience", ""))
            if exp and exp != "в описании":
                vac["RequiredExperience"] = exp

    def _execute_query(self, params: dict) -> list[Vacancy]:
        scraper = cloudscraper.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "desktop": True,
            }
        )

        try:
            response = scraper.get(
                "https://www.work.ua/jobs/",
                params=params,
                timeout=DEFAULT_PAGE_TIMEOUT,
            )
            safe_log(f"[Work.ua] URL: {response.url}")
            if response.status_code != 200:
                return []
        except Exception as e:
            safe_log(f"[Work.ua] Ошибка сбора: {e}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        jobs: list[Vacancy] = []

        cards = soup.find_all(
            "div",
            class_=lambda classes: classes and "card-hover" in classes,
        )

        for idx, card in enumerate(cards):
            try:
                h2 = card.find("h2")
                if not h2:
                    continue
                title_anchor = h2.find("a")
                if not title_anchor:
                    continue

                title = title_anchor.get_text(strip=True)
                url = title_anchor.get("href", "")
                if url and not url.startswith("http"):
                    url = "https://www.work.ua" + url

                company = "Неизвестно"
                company_div = card.find("div", class_=lambda c: c and ("company" in c or "strong-600" in c))
                if company_div:
                    company = company_div.get_text(strip=True)

                card_text = card.get_text(" ", strip=True)
                card_exp = normalize_experience_text(card_text)

                desc_p = card.find("p", class_=lambda c: c and ("ellipsis" in c or "text-default" in c or "overflow" in c or "text-muted" in c))
                desc = desc_p.get_text(" ", strip=True) if desc_p else ""

                salary = ""
                salary_tag = card.find("b", class_=lambda c: c and "strong-600" in c) or card.find("span", class_="strong-600")
                if salary_tag and any(char.isdigit() for char in salary_tag.text):
                    salary = salary_tag.get_text(strip=True)

                jobs.append({
                    "_temp_id": idx,
                    "Title": title,
                    "Company": company,
                    "Url": url,
                    "SalaryString": salary,
                    "DescriptionSnippet": desc[:1200],
                    "TechStack": "",
                    "AiSummary": "",
                    "AiMatchScore": 0,
                    "RequiredExperience": card_exp,
                })
            except Exception as exc:
                safe_log(f"[Work.ua] Ошибка парсинга карточки #{idx}: {exc}")
                continue

        return jobs
