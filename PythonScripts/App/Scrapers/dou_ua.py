from concurrent.futures import ThreadPoolExecutor
import re
import urllib.parse
from bs4 import BeautifulSoup
import cloudscraper

from App.config import DEFAULT_PAGE_TIMEOUT
from App.models import Vacancy, JobCriteria
from App.Scrapers.base import BaseScraper
from App.Scrapers.workua import extract_exp_from_text


def _fetch_single_dou_details(url: str) -> tuple[str, str]:
    """Fetch full description and experience from individual DOU vacancy page."""
    if not url:
        return "", ""
    try:
        scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "desktop": True})
        r = scraper.get(url, timeout=7)
        if r.status_code != 200:
            return "", ""
        soup = BeautifulSoup(r.text, "html.parser")
        desc_elem = soup.find("div", class_=lambda c: c and "b-typo" in c) or soup.find("div", class_=lambda c: c and "vacancy-section" in c)
        desc = desc_elem.get_text(" ", strip=True) if desc_elem else ""
        exp = extract_exp_from_text(desc)
        return desc, exp
    except Exception:
        return "", ""


class DouUaScraper(BaseScraper):
    """Scraper for jobs.dou.ua with XHR multi-filter and soft fallback support."""

    CATEGORY_MAP = {
        "c#": ".NET",
        ".net": ".NET",
        "dotnet": ".NET",
        "python": "Python",
        "py": "Python",
        "javascript": "Front End",
        "js": "Front End",
        "typescript": "Front End",
        "react": "Front End",
        "vue": "Front End",
        "angular": "Front End",
        "java": "Java",
        "kotlin": "Android",
        "android": "Android",
        "ios": "iOS/macOS",
        "swift": "iOS/macOS",
        "flutter": "Flutter",
        "php": "PHP",
        "c++": "C++",
        "cpp": "C++",
        "go": "Golang",
        "golang": "Golang",
        "rust": "Rust",
        "qa": "QA",
        "devops": "DevOps",
        "sql": "DBA",
    }

    @staticmethod
    def _clean_token(token: str) -> str:
        t = token.strip()
        t = re.sub(r'[сС](?=[#\+])', 'C', t)
        return t

    def fetch_jobs(self, keyword: str, criteria: JobCriteria | None = None) -> list[Vacancy]:
        raw_stacks = criteria.get_stack_list() if criteria else [s.strip() for s in keyword.split(",") if s.strip()]
        if not raw_stacks and keyword:
            raw_stacks = [keyword.strip()]

        cleaned_tokens = [self._clean_token(s) for s in raw_stacks if s]
        search_query = " ".join(cleaned_tokens[:2]) if cleaned_tokens else keyword.strip()

        matched_category = None
        for tok in cleaned_tokens:
            low = tok.lower()
            if low in self.CATEGORY_MAP:
                matched_category = self.CATEGORY_MAP[low]
                break

        # Primary query: search with descr=1 (search in vacancy descriptions)
        params: dict = {"descr": "1"}
        if search_query:
            params["search"] = search_query
        if matched_category:
            params["category"] = matched_category

        if criteria and criteria.is_remote():
            params["remote"] = "1"

        jobs = self._execute_query(params)

        # Soft fallback 1: if strict search returned < 4 jobs, try without category restriction
        if len(jobs) < 4 and matched_category:
            relaxed_params = {"search": search_query, "descr": "1"}
            if criteria and criteria.is_remote():
                relaxed_params["remote"] = "1"
            relaxed_jobs = self._execute_query(relaxed_params)
            existing_urls = {j.get("Url") for j in jobs}
            for rj in relaxed_jobs:
                if rj.get("Url") not in existing_urls:
                    jobs.append(rj)
                    existing_urls.add(rj.get("Url"))

        # Soft fallback 2: if still < 4, try primary single token
        if len(jobs) < 4 and cleaned_tokens:
            single_token = cleaned_tokens[0]
            if single_token != search_query:
                single_params = {"search": single_token, "descr": "1"}
                single_jobs = self._execute_query(single_params)
                existing_urls = {j.get("Url") for j in jobs}
                for rj in single_jobs:
                    if rj.get("Url") not in existing_urls:
                        jobs.append(rj)
                        existing_urls.add(rj.get("Url"))

        if jobs:
            self._enrich_jobs_details(jobs)

        return jobs

    def _enrich_jobs_details(self, jobs: list[Vacancy]) -> None:
        urls = [j.get("Url", "") for j in jobs]
        if not any(urls):
            return

        with ThreadPoolExecutor(max_workers=min(6, len(jobs))) as executor:
            details_list = list(executor.map(_fetch_single_dou_details, urls))

        for vac, (full_desc, exp) in zip(jobs, details_list):
            if full_desc:
                vac["DescriptionSnippet"] = full_desc[:1500]
            if exp:
                vac["RequiredExperience"] = exp

    def _execute_query(self, params: dict) -> list[Vacancy]:
        scraper = cloudscraper.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "desktop": True,
            }
        )

        query_str = urllib.parse.urlencode(params)
        base_url = f"https://jobs.dou.ua/vacancies/?{query_str}" if query_str else "https://jobs.dou.ua/vacancies/"

        try:
            r = scraper.get(base_url, timeout=DEFAULT_PAGE_TIMEOUT)
            print(f"[DOU] URL: {r.url}")
            if r.status_code != 200:
                return []

            csrf = scraper.cookies.get("csrftoken", "")
            headers = {
                "X-Requested-With": "XMLHttpRequest",
                "Referer": base_url,
            }
            data = {"csrfmiddlewaretoken": csrf, "count": 0}
            xhr_url = f"https://jobs.dou.ua/vacancies/xhr-load/?{query_str}" if query_str else "https://jobs.dou.ua/vacancies/xhr-load/"

            resp = scraper.post(xhr_url, data=data, headers=headers, timeout=DEFAULT_PAGE_TIMEOUT)
            if resp.status_code != 200:
                return []

            html = resp.json().get("html", "")
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            print(f"[DOU] Ошибка сбора: {e}")
            return []

        jobs: list[Vacancy] = []
        cards = soup.find_all("li", class_=lambda c: c and ("l-vacancy" in c or "vacancy" in c))

        for idx, card in enumerate(cards):
            try:
                title_elem = card.find("a", class_="vt")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                url = title_elem.get("href", "")
                if url and not url.startswith("http"):
                    url = "https://jobs.dou.ua" + url

                company_elem = card.find("a", class_="company")
                company = company_elem.get_text(strip=True) if company_elem else "Неизвестно"

                desc_elem = card.find("div", class_="sh-info")
                desc = desc_elem.get_text(" ", strip=True) if desc_elem else ""

                salary_elem = card.find("span", class_="salary")
                salary = salary_elem.get_text(strip=True) if salary_elem else ""

                card_exp = extract_exp_from_text(desc)

                jobs.append({
                    "_temp_id": idx,
                    "Title": title,
                    "Company": company.replace("\xa0", " "),
                    "Url": url,
                    "SalaryString": salary,
                    "DescriptionSnippet": desc[:1200],
                    "TechStack": "",
                    "AiSummary": "",
                    "AiMatchScore": 0,
                    "RequiredExperience": card_exp,
                })
            except Exception as e:
                print(f"[DOU] Ошибка парсинга карточки #{idx}: {e}")
                continue

        return jobs
