import json
import random
import re
import threading
import time
from collections.abc import Callable
from html.parser import HTMLParser

from openai import OpenAI

from App.AI.prompt_loader import load_prompt
from App.config import (
    DEFAULT_OPENROUTER_MODEL,
    OPENROUTER_MODEL_FALLBACK_CHAIN,
    get_live_openrouter_free_models,
    OPENROUTER_BASE_URL,
    ROLE_WEIGHT,
    LEVEL_WEIGHT,
    TECH_WEIGHT,
    EXPERIENCE_WEIGHT,
    FATAL_ERROR_SIGNALS,
)
from App.models import Vacancy, JobCriteria
from App.utils import safe_log, normalize_experience_text

BATCH_SIZE = 5

# ─────────────────────────────────────────────────────────────────────────────
# Multilingual rotating loading phrases (cycles every ~2s while AI is thinking)
# ─────────────────────────────────────────────────────────────────────────────
THINKING_PHRASES_UK = [
    "Аналізуємо вимоги роботодавця...",
    "Зіставляємо ваш досвід із вакансією...",
    "Перевіряємо відповідність навичок...",
    "Звіряємо технологічний стек...",
    "Оцінюємо вимоги до досвіду...",
    "Аналізуємо рівень позиції...",
    "Вивчаємо деталі вакансії...",
    "Шукаємо збіги з вашим профілем...",
    "Перевіряємо ключові вимоги...",
    "Оцінюємо відповідність позиції...",
    "Аналізуємо умови роботи...",
    "Зіставляємо вимоги та навички...",
    "Перевіряємо додаткові умови...",
    "Оцінюємо перспективність вакансії...",
    "Шукаємо важливі деталі в описі...",
    "Зважуємо критерії відповідності...",
    "Перевіряємо можливі невідповідності...",
    "Порівнюємо вакансію з вашим профілем...",
    "Оцінюємо ключові параметри...",
    "Аналізуємо вимоги до кандидата...",
    "Перевіряємо технологічні вимоги...",
    "Оцінюємо релевантність вашого досвіду...",
    "Формуємо оцінку відповідності...",
    # Великодки
    "Гладимо котика...",
    "Робимо перерву на каву...",
    "Шукаємо того самого кандидата... здається, це ви.",
    "Сидимо у тік-тоці...",
    "Звіряємо вимоги... і робимо вигляд, що все під контролем.",
]

THINKING_PHRASES_EN = [
    "Analyzing employer requirements...",
    "Matching your experience with the job...",
    "Verifying required skill set...",
    "Checking technology stack fit...",
    "Evaluating experience expectations...",
    "Assessing seniority level requirements...",
    "Reviewing vacancy details...",
    "Finding matches with your profile...",
    "Checking core job requirements...",
    "Evaluating candidate-to-job match...",
    "Analyzing work conditions...",
    "Comparing skills and prerequisites...",
    "Reviewing perks and additional conditions...",
    "Evaluating position prospects...",
    "Extracting key details from description...",
    "Weighing match criteria...",
    "Checking potential discrepancies...",
    "Comparing position against your profile...",
    "Assessing key parameters...",
    "Analyzing candidate expectations...",
    "Verifying tech requirements...",
    "Evaluating relevance of your experience...",
    "Formulating final match score...",
    # Easter eggs
    "Petting the cat...",
    "Brewing a quick cup of coffee...",
    "Searching for the perfect candidate... looks like it's you.",
    "Watching TikTok",
    "Reviewing requirements... and pretending everything is under control.",
]


class _Stripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_text(self):
        return "".join(self.fed)


class AiEvaluator:
    """
    Evaluates vacancies in batches via OpenRouter free LLMs.
    Auto-switches to fallback model on 429 rate limits, fatal errors, or parse errors.
    Retains dead model registry across batches to prevent recurring failures.
    """

    def __init__(self, api_key: str, model: str | None = None):
        if not api_key:
            raise ValueError("API key не указан.")

        self.api_key = api_key.strip()
        self.on_model_switch: Callable[[str, str], None] | None = None
        self.base_url = OPENROUTER_BASE_URL
        self._dead_models: set[str] = set()
        self._fallback_chain_original: list[str] = get_live_openrouter_free_models()
        self.model: str = model or (self._fallback_chain_original[0] if self._fallback_chain_original else DEFAULT_OPENROUTER_MODEL)
        self.provider = "OpenRouter"

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
        criteria: JobCriteria,
        on_progress: Callable[[int, str], None] | None = None,
    ) -> list[Vacancy]:
        """
        Evaluate all vacancies in batches with progress notifications.
        """
        if not vacancies:
            return []

        total = len(vacancies)
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        evaluated_vacancies: list[Vacancy] = []

        safe_log(f"[AI] Анализируем {total} вакансий через {self.provider} ({self.model})...")

        lang = (criteria.language or "").lower()
        if "en" in lang or "eng" in lang:
            phrases = THINKING_PHRASES_EN
            batch_progress_tmpl = "AI analyzing batch {batch_num}/{total_batches} (jobs {start_idx}–{end_idx})..."
            batch_done_tmpl = "Batch {batch_num}/{total_batches} ready — analyzed {done_count}/{total}"
            batch_phrase_tmpl = "{phrase} (batch {batch_num}/{total_batches})"
        else:
            phrases = THINKING_PHRASES_UK
            batch_progress_tmpl = "ШІ аналізує батч {batch_num}/{total_batches} (вакансії {start_idx}–{end_idx})..."
            batch_done_tmpl = "Батч {batch_num}/{total_batches} готовий — проаналізовано {done_count}/{total}"
            batch_phrase_tmpl = "{phrase} (батч {batch_num}/{total_batches})"

        last_phrase_idx: int = -1

        def pick_random_phrase() -> str:
            nonlocal last_phrase_idx
            available = [i for i in range(len(phrases)) if i != last_phrase_idx]
            chosen_idx = random.choice(available) if available else 0
            last_phrase_idx = chosen_idx
            return phrases[chosen_idx]

        for batch_num in range(1, total_batches + 1):
            start = (batch_num - 1) * BATCH_SIZE
            batch_raw = vacancies[start: start + BATCH_SIZE]

            # Copy dict so original input list is never mutated
            batch = [{**vac, "_temp_id": start + idx} for idx, vac in enumerate(batch_raw)]

            vacancies_text = self._build_batch_text(batch)
            prompt = load_prompt(
                criteria=criteria,
                vacancies_text=vacancies_text,
            )

            pct_start = 15 + int(((batch_num - 1) / total_batches) * 75)
            pct_end = 15 + int((batch_num / total_batches) * 75)

            if on_progress:
                on_progress(
                    pct_start,
                    batch_progress_tmpl.format(
                        batch_num=batch_num,
                        total_batches=total_batches,
                        start_idx=start + 1,
                        end_idx=min(start + len(batch), total),
                    ),
                )

            result_holder: list = []
            error_holder: list = []

            def do_ai_call(p=prompt, rh=result_holder, eh=error_holder):
                try:
                    rh.append(self._request_ai_with_retry(p))
                except Exception as e:
                    eh.append(e)

            ai_thread = threading.Thread(target=do_ai_call, daemon=True)
            ai_thread.start()

            t0 = time.time()
            while ai_thread.is_alive():
                ai_thread.join(timeout=2.0)
                if ai_thread.is_alive() and on_progress:
                    elapsed = time.time() - t0
                    frac = min(elapsed / 15.0, 0.90)
                    tick_pct = min(
                        int(pct_start + frac * (pct_end - pct_start)),
                        pct_end - 1,
                    )
                    phrase = pick_random_phrase()
                    on_progress(tick_pct, batch_phrase_tmpl.format(phrase=phrase, batch_num=batch_num, total_batches=total_batches))

            elapsed_total = time.time() - t0

            if error_holder:
                safe_log(f"  [ERROR] Сбой батча {batch_num}: {error_holder[0]}")
                evaluated_vacancies.extend([self._fallback_vacancy(v) for v in batch])
            else:
                ai_results = result_holder[0] if result_holder else []
                merged = self._merge_results(batch, ai_results)
                evaluated_vacancies.extend(merged)
                safe_log(
                    f"  [AI] Батч {batch_num}/{total_batches} готов за "
                    f"{elapsed_total:.2f}с (распознано {len(ai_results)}/{len(batch)})"
                )

            if on_progress:
                on_progress(
                    pct_end,
                    batch_done_tmpl.format(
                        batch_num=batch_num,
                        total_batches=total_batches,
                        done_count=len(evaluated_vacancies),
                        total=total,
                    ),
                )

            if start + BATCH_SIZE < total:
                time.sleep(0.5)

        return evaluated_vacancies

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _request_ai_with_retry(self, prompt: str, max_retries: int | None = None) -> list[dict]:
        """
        Retries through the model fallback chain.
        Switches model immediately on 429 rate limits, fatal errors, and parse failures.
        Never retries models already known to be dead in this session.
        """
        local_chain: list[str] = [m for m in self._fallback_chain_original if m not in self._dead_models]
        if not local_chain:
            local_chain = list(self._fallback_chain_original)
            self._dead_models.clear()

        if self.model in self._dead_models and local_chain:
            self.model = local_chain[0]
        current_model = self.model

        if max_retries is None:
            max_retries = max(len(local_chain) + 2, 6)

        last_exc: Exception | None = None
        attempt = 0
        while attempt < max_retries:
            attempt += 1
            try:
                kwargs: dict = {
                    "model": current_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.05,
                    "max_tokens": 4096,
                    "timeout": 35,
                }
                if local_chain:
                    server_fallbacks = [m for m in local_chain if m != current_model and m not in self._dead_models][:2]
                    if server_fallbacks:
                        kwargs["extra_body"] = {"models": server_fallbacks}

                response = self.client.chat.completions.create(**kwargs)
                raw_content = response.choices[0].message.content or ""

                preview = raw_content[:180].replace("\n", " ")
                safe_log(f"    [RAW] Model reply preview: {preview}")

                results = self._extract_results(raw_content)
                safe_log(f"    [PARSE] Extracted {len(results)} items from response")

                if len(results) == 0:
                    raise ValueError("ParseError: Model returned 0 valid JSON items")

                # Persist succeeding model
                self.model = current_model
                return results

            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()

                is_fatal = any(sig in err_str for sig in FATAL_ERROR_SIGNALS)
                is_rate_limit = (
                    "429" in err_str
                    or "rate_limit" in err_str
                    or "quota" in err_str
                    or "temporarily rate-limited" in err_str
                )
                is_parse_error = "parseerror" in err_str

                # Fail-fast to next fallback model
                if (is_fatal or is_rate_limit or is_parse_error) and local_chain:
                    self._dead_models.add(current_model)
                    if current_model in local_chain:
                        local_chain.remove(current_model)

                    if local_chain:
                        old_model = current_model
                        current_model = local_chain[0]
                        self.model = current_model
                        reason = "Rate limited (429)" if is_rate_limit else "Fatal error" if is_fatal else "Parse error"
                        safe_log(f"    [FAIL-FAST] {reason} on {old_model} → switching to {current_model}")
                        if self.on_model_switch:
                            self.on_model_switch(old_model, current_model)
                        continue
                    else:
                        safe_log("    [ERROR] Все резервные модели исчерпаны.")

                wait = min(attempt * 2.0, 6.0)
                safe_log(f"    [WARN] Попытка {attempt}/{max_retries}: ожидание {wait:.1f}с... ({exc})")
                time.sleep(wait)

        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _extract_results(text: str) -> list[dict]:
        """
        Robust multi-layer JSON parser.
        Handles: <think> tags, markdown code blocks, wrapped objects,
        plain arrays, and partial/malformed JSON.
        """
        if not text:
            return []

        clean_text = text.strip()

        # Step 0: Strip reasoning/thinking tags
        clean_text = re.sub(r"<think>.*?</think>", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"<thinking>.*?</thinking>", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"<reasoning>.*?</reasoning>", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = clean_text.strip()

        # Step 1: Strip markdown code fences
        if "```json" in clean_text:
            clean_text = clean_text.split("```json", 1)[1]
            if "```" in clean_text:
                clean_text = clean_text.split("```", 1)[0]
        elif "```" in clean_text:
            parts = clean_text.split("```")
            clean_text = parts[1] if len(parts) >= 3 else clean_text.replace("```", "")
        clean_text = clean_text.strip()

        # Step 2: Direct JSON parse
        try:
            parsed = json.loads(clean_text, strict=False)
            if isinstance(parsed, list):
                return [p for p in parsed if isinstance(p, dict)]
            if isinstance(parsed, dict):
                for key in ("results", "data", "vacancies", "items", "output"):
                    if isinstance(parsed.get(key), list):
                        return [p for p in parsed[key] if isinstance(p, dict)]
                if "temp_id" in parsed:
                    return [parsed]
                for val in parsed.values():
                    if isinstance(val, list) and val:
                        return [p for p in val if isinstance(p, dict)]
        except Exception:
            pass

        # Step 3: Find outermost JSON array or object
        bracket_match = re.search(r"\[[\s\S]*\]", clean_text)
        if bracket_match:
            try:
                parsed = json.loads(bracket_match.group(0), strict=False)
                if isinstance(parsed, list):
                    return [p for p in parsed if isinstance(p, dict)]
            except Exception:
                pass

        obj_matches = re.findall(r"\{[^{}]*\}", clean_text)
        extracted = []
        for obj_str in obj_matches:
            try:
                obj = json.loads(obj_str, strict=False)
                if isinstance(obj, dict) and "temp_id" in obj:
                    extracted.append(obj)
            except Exception:
                continue

        return extracted

    @staticmethod
    def _extract_fallback_tech(title: str, desc: str | None) -> str:
        text = f"{title} {desc or ''}".lower()
        known = [
            "c#", ".net", "asp.net", "wpf", "wcf", "sql", "python", "django", "fastapi",
            "flask", "javascript", "typescript", "react", "vue", "angular", "node.js",
            "java", "spring", "go", "golang", "rust", "c++", "cpp", "docker",
            "kubernetes", "aws", "azure", "gcp", "flutter", "ios", "swift",
            "android", "kotlin", "qa", "qa automation", "cypress", "selenium", "creatio",
            "umbraco", "html", "css", "tailwind", "next.js", "graphql", "redis", "postgresql",
        ]
        found = []
        for k in known:
            pattern = rf"(?:^|[\s,.\-—/(){{}}[\]]){re.escape(k)}(?:$|[\s,.\-—/(){{}}[\]])"
            if re.search(pattern, text):
                clean_k = k.upper() if k in ("sql", "aws", "gcp", "qa", "css", "html", "ios", "wpf", "wcf") else k.title()
                if clean_k not in found:
                    found.append(clean_k)

        return ", ".join(found[:6]) if found else "Не указано"

    @classmethod
    def _fallback_vacancy(cls, vac: Vacancy) -> Vacancy:
        score = 65
        title = vac.get("Title", "")
        desc = vac.get("DescriptionSnippet", "")
        orig_stack = vac.get("TechStack", "").strip()
        stack = orig_stack if orig_stack else cls._extract_fallback_tech(title, desc)
        orig_exp = vac.get("RequiredExperience", "").strip()
        exp = normalize_experience_text(orig_exp or desc)

        result: Vacancy = {
            "Title": title,
            "Company": vac.get("Company", "Неизвестно"),
            "Url": vac.get("Url", ""),
            "SalaryString": vac.get("SalaryString", ""),
            "RequiredExperience": exp,
            "TechStack": stack,
            "AiSummary": "Автоматическая оценка (базовый анализ требований).",
            "AiMatchScore": score,
        }
        if "Source" in vac:
            result["Source"] = vac["Source"]
        return result

    @staticmethod
    def _sanitize_text(text: str) -> str:
        if not text:
            return ""
        stripper = _Stripper()
        stripper.feed(text)
        clean = stripper.get_text()
        clean = " ".join(clean.split())
        clean = clean.replace('"', "'")
        return clean[:1200]

    @classmethod
    def _build_batch_text(cls, vacancies: list[Vacancy]) -> str:
        parts = []
        for v in vacancies:
            tid = v.get("_temp_id", 0)
            title = v.get("Title", "")
            exp = v.get("RequiredExperience", "")
            stack = v.get("TechStack", "")
            desc = cls._sanitize_text(v.get("DescriptionSnippet", "") or "")
            stack_info = f" | Стек: {stack}" if stack else ""
            exp_info = f" | Опыт: {exp}" if exp else ""
            parts.append(f"[ID: {tid}] Должность: {title}{stack_info}{exp_info} | Описание: {desc}")
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

        for res in ai_results:
            if isinstance(res, dict):
                tid = res.get("temp_id")
                if tid is not None:
                    try:
                        result_map[int(tid)] = res
                    except (ValueError, TypeError):
                        pass

        merged: list[Vacancy] = []
        for vac in vacancies:
            tid = vac.get("_temp_id")
            res = result_map.get(tid)
            if not res:
                merged.append(cls._fallback_vacancy(vac))
                continue

            updated = dict(vac)
            ai_tech = res.get("TechStack", "")
            if isinstance(ai_tech, list):
                ai_tech = ", ".join(str(t) for t in ai_tech)
            ai_tech_str = str(ai_tech).strip()

            orig_stack = updated.get("TechStack", "").strip()
            if ai_tech_str and ai_tech_str not in ("Не указано", "не указано", "-"):
                updated["TechStack"] = ai_tech_str
            elif orig_stack:
                updated["TechStack"] = orig_stack
            else:
                updated["TechStack"] = cls._extract_fallback_tech(updated.get("Title", ""), vac.get("DescriptionSnippet", ""))

            updated["AiSummary"] = str(res.get("AiSummary", "Не удалось проанализировать"))
            updated["AiMatchScore"] = cls._calculate_score(res)

            extracted_exp = str(res.get("ExtractedExperience", "")).strip()
            current_exp = updated.get("RequiredExperience", "").strip()
            if extracted_exp and extracted_exp not in ("Не указано", "-"):
                updated["RequiredExperience"] = normalize_experience_text(extracted_exp)
            elif current_exp:
                updated["RequiredExperience"] = normalize_experience_text(current_exp)
            else:
                updated["RequiredExperience"] = "в описании"

            updated.pop("_temp_id", None)
            updated.pop("DescriptionSnippet", None)
            merged.append(updated)

        return merged
