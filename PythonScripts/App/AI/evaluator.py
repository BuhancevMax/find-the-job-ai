import json
import re
import sys
import time
from openai import OpenAI

from App.AI.prompt_loader import load_prompt
from App.config import (
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_GROQ_MODEL,
    DEFAULT_OPENROUTER_MODEL,
    DEEPSEEK_BASE_URL,
    EXPERIENCE_WEIGHT,
    GROQ_BASE_URL,
    LEVEL_WEIGHT,
    OPENROUTER_BASE_URL,
    ROLE_WEIGHT,
    TECH_WEIGHT,
)
from App.models import Vacancy


def safe_log(msg: str):
    """Safely print messages on any Windows console encoding."""
    try:
        print(msg)
    except UnicodeEncodeError:
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass


class AiEvaluator:
    """
    Evaluates all vacancies in a single batch request with bulletproof
    JSON and regex extraction for maximum speed and 100% reliability.
    """

    def __init__(self, api_key: str, model: str | None = None):
        if not api_key:
            raise ValueError("API key не указан.")

        self.api_key = api_key.strip()

        if self.api_key.startswith("gsk_"):
            self.base_url = GROQ_BASE_URL
            self.model = model or DEFAULT_GROQ_MODEL
            self.provider = "Groq"
        elif self.api_key.startswith("sk-or-"):
            self.base_url = OPENROUTER_BASE_URL
            self.model = model or DEFAULT_OPENROUTER_MODEL
            self.provider = "OpenRouter"
        else:
            self.base_url = DEEPSEEK_BASE_URL
            self.model = model or DEFAULT_DEEPSEEK_MODEL
            self.provider = "DeepSeek"

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_vacancies(
        self,
        vacancies: list[Vacancy],
        target_role: str,
        target_exp: str,
        language: str,
    ) -> list[Vacancy]:
        if not vacancies:
            return []

        total = len(vacancies)
        safe_log(f"[AI] Отправляем единый батч из {total} вакансий в {self.provider} ({self.model})...")

        for idx, vac in enumerate(vacancies):
            vac["_temp_id"] = idx

        vacancies_text = self._build_batch_text(vacancies)

        prompt = load_prompt(
            target_role=target_role,
            target_exp=target_exp,
            language=language,
            vacancies_text=vacancies_text,
        )

        try:
            start_time = time.time()
            ai_results = self._request_ai_with_retry(prompt)
            elapsed = time.time() - start_time
            safe_log(f"  [AI] Ответ получен за {elapsed:.2f} сек (распознано {len(ai_results)}/{total})!")
            return self._merge_results(vacancies, ai_results)
        except Exception as exc:
            safe_log(f"  [ERROR] Ошибка общего батча: {exc}")
            return [self._fallback_vacancy(v) for v in vacancies]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _request_ai_with_retry(self, prompt: str, max_retries: int = 3) -> list[dict]:
        last_exc: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=4096,
                )

                raw_content = response.choices[0].message.content or ""
                return self._extract_results(raw_content)
            except Exception as exc:
                last_exc = exc
                wait = attempt * 2.0
                safe_log(f"    [WARN] Попытка {attempt}/{max_retries}: повтор через {wait:.1f}с... ({exc})")
                time.sleep(wait)

        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _extract_results(text: str) -> list[dict]:
        """Robust multi-layer JSON parser with regex fallback."""
        if not text:
            return []

        clean_text = text.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```", 1)[1].split("```", 1)[0].strip()

        # 1. Try full JSON parse
        try:
            parsed = json.loads(clean_text, strict=False)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                for key in ("results", "data", "vacancies", "items"):
                    if isinstance(parsed.get(key), list):
                        return parsed[key]
                for val in parsed.values():
                    if isinstance(val, list):
                        return val
        except Exception:
            pass

        # 2. Extract item by item with regex
        items: list[dict] = []
        pattern = re.compile(r'\{\s*"temp_id"\s*:\s*(\d+).*?\}', re.DOTALL)
        for match in pattern.finditer(clean_text):
            chunk = match.group(0)
            try:
                item = json.loads(chunk, strict=False)
                if isinstance(item, dict):
                    items.append(item)
                    continue
            except Exception:
                pass

            # Lenient field extraction
            try:
                tid = int(match.group(1))
                item_dict = {"temp_id": tid}

                for field in ["role_match", "level_match", "tech_match", "experience_match"]:
                    m = re.search(rf'"{field}"\s*:\s*(\d+)', chunk)
                    if m:
                        item_dict[field] = int(m.group(1))

                for field in ["TechStack", "AiSummary", "ExtractedExperience"]:
                    m = re.search(rf'"{field}"\s*:\s*"(.*?)"(?:\s*,\s*"|\s*}})', chunk, re.DOTALL)
                    if m:
                        item_dict[field] = m.group(1)

                m_crit = re.search(r'"critical_mismatch"\s*:\s*(true|false)', chunk, re.IGNORECASE)
                if m_crit:
                    item_dict["critical_mismatch"] = (m_crit.group(1).lower() == "true")

                items.append(item_dict)
            except Exception:
                continue

        return items

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Strip HTML tags and problematic characters."""
        if not text:
            return ""

        from html.parser import HTMLParser

        class _Stripper(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self._parts: list[str] = []

            def handle_data(self, data: str) -> None:
                self._parts.append(data)

            def get_text(self) -> str:
                return " ".join(self._parts)

        stripper = _Stripper()
        stripper.feed(text)
        clean = stripper.get_text()
        clean = " ".join(clean.split())
        clean = clean.replace('"', "'")
        return clean[:300]

    @classmethod
    def _build_batch_text(cls, vacancies: list[Vacancy]) -> str:
        parts = []
        for v in vacancies:
            tid = v.get("_temp_id", 0)
            title = v.get("Title", "")
            exp = v.get("RequiredExperience", "")
            desc = cls._sanitize_text(v.get("DescriptionSnippet", "") or "")
            parts.append(f"[ID: {tid}] Должность: {title} | Опыт: {exp} | Описание: {desc}")
        return "\n".join(parts)

    @staticmethod
    def _calculate_score(result: dict) -> int:
        try:
            r_match = int(result.get("role_match", 0))
            l_match = int(result.get("level_match", 0))
            t_match = int(result.get("tech_match", 0))
            e_match = int(result.get("experience_match", 0))
        except (ValueError, TypeError):
            r_match, l_match, t_match, e_match = 0, 0, 0, 0

        weighted_score = (
            r_match * ROLE_WEIGHT
            + l_match * LEVEL_WEIGHT
            + t_match * TECH_WEIGHT
            + e_match * EXPERIENCE_WEIGHT
        )

        score = max(0, min(100, round(weighted_score)))

        if result.get("critical_mismatch") and score > 30:
            score = min(score, 30)

        return score

    @classmethod
    def _merge_results(cls, vacancies: list[Vacancy], ai_results: list[dict]) -> list[Vacancy]:
        result_map: dict[int, dict] = {}

        for idx, res in enumerate(ai_results):
            if isinstance(res, dict):
                tid = res.get("temp_id")
                if tid is not None:
                    try:
                        result_map[int(tid)] = res
                    except (ValueError, TypeError):
                        result_map[idx] = res
                else:
                    result_map[idx] = res

        merged: list[Vacancy] = []
        for idx, vac in enumerate(vacancies):
            res = result_map.get(idx)
            if not res:
                merged.append(cls._fallback_vacancy(vac))
                continue

            updated = dict(vac)
            tech = res.get("TechStack", "")
            if isinstance(tech, list):
                tech = ", ".join(str(t) for t in tech)
            updated["TechStack"] = str(tech) or "Не указано"
            updated["AiSummary"] = str(res.get("AiSummary", "Не удалось проанализировать"))
            updated["AiMatchScore"] = cls._calculate_score(res)

            extracted_exp = str(res.get("ExtractedExperience", "")).strip()
            if updated.get("RequiredExperience") == "Смотреть в описании" and extracted_exp:
                updated["RequiredExperience"] = extracted_exp

            updated.pop("_temp_id", None)
            updated.pop("DescriptionSnippet", None)
            merged.append(updated)

        return merged

    @staticmethod
    def _fallback_vacancy(vacancy: Vacancy) -> Vacancy:
        fallback = dict(vacancy)
        fallback.update({
            "TechStack": "Ошибка анализа",
            "AiSummary": "Не удалось проанализировать вакансию",
            "AiMatchScore": 0,
        })
        fallback.pop("_temp_id", None)
        fallback.pop("DescriptionSnippet", None)
        return fallback
