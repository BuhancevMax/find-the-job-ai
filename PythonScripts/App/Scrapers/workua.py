from concurrent.futures import ThreadPoolExecutor
import re
from bs4 import BeautifulSoup
import cloudscraper

from App.config import DEFAULT_PAGE_TIMEOUT, SCRAPER_USER_AGENT
from App.models import Vacancy, JobCriteria
from App.Scrapers.base import BaseScraper


def extract_exp_from_text(text: str) -> str:
    """Extract experience requirement from text in UA/RU/EN and normalize to clean Russian format."""
    if not text:
        return "в описании"
    t = text.strip().lower()

    if "без" in t or "no experience" in t or "trainee" in t or "студент" in t:
        return "без опыта"
    if "в описі" in t or "в описании" in t or t == "не указано":
        return "в описании"

    # Match 0.5 year / 6 months / 0.5 року
    if re.search(r'(0[.,]5|пів|пол|6\s*міс|6\s*мес)', t):
        return "до 1 года"

    # Match range e.g. '1-3 года', '1-3 роки', '2-5 years', '1–3y'
    range_match = re.search(r'(\d+)\s*[-–]\s*(\d+)\s*(?:years?|yrs?|yr|років|роки|року|лет|года|год|y)?', t)
    if range_match:
        n1, n2 = range_match.group(1), range_match.group(2)
        return f"{n1}-{n2} года"

    # Match '5+ years', '5+ лет', '3+ роки'
    plus_match = re.search(r'(\d+)\s*\+\s*(?:years?|yrs?|yr|років|роки|року|лет|года|год|y)?', t)
    if plus_match:
        n = int(plus_match.group(1))
        unit = "год" if n == 1 else "года" if 2 <= n <= 4 else "лет"
        return f"{n}+ {unit}"

    # Match 'от X лет', 'від X років', 'from X years'
    from_match = re.search(r'(?:від|от|from|більше|более)\s*(\d+)\s*(?:years?|yrs?|yr|років|роки|року|лет|года|год|y)?', t)
    if from_match:
        n = int(from_match.group(1))
        unit = "года" if n == 1 else "лет"
        return f"от {n} {unit}"

    # Match single number e.g. '1 year', '2 роки', '5 years', '5 лет'
    num_match = re.search(r'(?:досвід|опыт|experience|вимоги)?\D*(\d+)\s*(?:years?|yrs?|yr|років|роки|року|лет|года|год|y)', t)
    if num_match:
        n = int(num_match.group(1))
        unit = "год" if (n % 10 == 1 and n % 100 != 11) else "года" if (2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20)) else "лет"
        return f"{n} {unit}"

    return "в описании"


def _fetch_single_workua_details(url: str) -> tuple[list[str], str, str]:
    """Fetch skills, full description and conditions from individual Work.ua page."""
    try:
        scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "desktop": True})
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

    @staticmethod
    def _clean_token(token: str) -> str:
        t = token.strip()
        t = re.sub(r'[сС](?=[#\+])', 'C', t)
        return t

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

        cleaned_tokens = [self._clean_token(s) for s in raw_stacks if s]
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

        with ThreadPoolExecutor(max_workers=min(6, len(jobs))) as executor:
            details_list = list(executor.map(_fetch_single_workua_details, urls))

        for vac, (skills, full_desc, cond_text) in zip(jobs, details_list):
            if skills:
                vac["TechStack"] = ", ".join(skills)
            if full_desc:
                vac["DescriptionSnippet"] = full_desc[:1500]
            
            # Extract experience from conditions or description if not set
            exp = extract_exp_from_text(cond_text) or extract_exp_from_text(full_desc) or vac.get("RequiredExperience", "")
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

        try:
            response = scraper.get(
                "https://www.work.ua/jobs/",
                params=params,
                timeout=DEFAULT_PAGE_TIMEOUT,
            )
            print(f"[Work.ua] URL: {response.url}")
            if response.status_code != 200:
                return []
        except Exception as e:
            print(f"[Work.ua] Ошибка сбора: {e}")
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

                # Company name
                company = "Неизвестно"
                company_div = card.find("div", class_=lambda c: c and ("company" in c or "strong-600" in c))
                if company_div:
                    company = company_div.get_text(strip=True)

                # Card description snippet & experience
                card_text = card.get_text(" ", strip=True)
                card_exp = extract_exp_from_text(card_text)

                desc_p = card.find("p", class_=lambda c: c and ("ellipsis" in c or "text-default" in c or "overflow" in c or "text-muted" in c))
                desc = desc_p.get_text(" ", strip=True) if desc_p else ""

                # Salary
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
                print(f"[Work.ua] Ошибка парсинга карточки #{idx}: {exc}")
                continue

        return jobs
