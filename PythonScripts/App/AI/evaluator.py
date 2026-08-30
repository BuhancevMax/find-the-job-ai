import json
import random
import re
import threading
import time
from collections.abc import Callable

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
from App.models import Vacancy, JobCriteria, AIEvaluation

BATCH_SIZE = 5

# ─────────────────────────────────────────────────────────────────────────────
# Rotating loading phrases — cycled every ~2s while AI is thinking.
# Adds life to the progress bar so it never looks stuck.
# ─────────────────────────────────────────────────────────────────────────────
THINKING_PHRASES = [
    "Анализируем требования работодателя...",
    "Сопоставляем ваш опыт с вакансией...",
    "Проверяем соответствие навыков...",
    "Сверяем технологический стек...",
    "Оцениваем требования к опыту...",
    "Анализируем уровень позиции...",
    "Изучаем детали вакансии...",
    "Ищем совпадения с вашим профилем...",
    "Проверяем ключевые требования...",
    "Оцениваем соответствие позиции...",
    "Анализируем условия работы...",
    "Сопоставляем требования и навыки...",
    "Проверяем дополнительные условия...",
    "Оцениваем перспективность вакансии...",
    "Ищем важные детали в описании...",
    "Взвешиваем критерии соответствия...",
    "Проверяем возможные несоответствия...",
    "Сравниваем вакансию с вашим профилем...",
    "Оцениваем ключевые параметры...",
    "Анализируем требования к кандидату...",
    "Проверяем технологические требования...",
    "Оцениваем релевантность вашего опыта...",
    "Формируем оценку соответствия...",
    # Пасхалки
    "Проверяем, не спрятали ли тут зарплату в 8 пункте...",
    "Делаем перерыв на кофе...",
    "Ищем того самого кандидата... кажется, это вы.",
    "Проверяем, действительно ли нужен 'молодой специалист с 10 годами опыта'...",
    "Сверяем требования... и делаем вид, что всё под контролем.",
    "ИИ делает вид, что не заметил 'стрессоустойчивость' в требованиях...",
]


def safe_log(msg: str) -> None:
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
    Evaluates vacancies in batches via OpenRouter free LLMs.
    Auto-switches to fallback model on 429 or parse error.
    """

    def __init__(self, api_key: str, model: str | None = None):
        if not api_key:
            raise ValueError("API key не указан.")

        self.api_key = api_key.strip()
        # Callback fired when a model switch happens (streaming mode)
        self.on_model_switch: Callable[[str, str], None] | None = None

        self.base_url = OPENROUTER_BASE_URL
        self._fallback_chain_original = get_live_openrouter_free_models()
        self.model = model or (self._fallback_chain_original[0] if self._fallback_chain_original else DEFAULT_OPENROUTER_MODEL)
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
        Evaluate all vacancies, processing them in batches.

        on_progress(percent: int, message: str) is called:
          - at start of each batch (pct_start)
          - every ~2s while the AI is thinking (smooth crawl with random non-repeating phrase)
          - at end of each batch (pct_end)
        """
        if not vacancies:
            return []

        total = len(vacancies)
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        evaluated_vacancies: list[Vacancy] = []

        safe_log(f"[AI] Анализируем {total} вакансий через {self.provider} ({self.model})...")

        last_phrase_idx: int = -1

        def pick_random_phrase() -> str:
            nonlocal last_phrase_idx
            available = [i for i in range(len(THINKING_PHRASES)) if i != last_phrase_idx]
            chosen_idx = random.choice(available) if available else 0
            last_phrase_idx = chosen_idx
            return THINKING_PHRASES[chosen_idx]

        for batch_num in range(1, total_batches + 1):
            start = (batch_num - 1) * BATCH_SIZE
            batch_raw = vacancies[start: start + BATCH_SIZE]

            # Fix #8: use dict copy so original list is never mutated
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
                    f"ИИ анализирует батч {batch_num}/{total_batches} "
                    f"(вакансии {start + 1}–{min(start + len(batch), total)})...",
                )

            # --- Run AI call in a thread; tick progress while waiting ---
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
                    on_progress(tick_pct, f"{phrase} (батч {batch_num}/{total_batches})")

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
                    f"Батч {batch_num}/{total_batches} готов — "
                    f"проанализировано {len(evaluated_vacancies)}/{total}",
                )

            if start + BATCH_SIZE < total:
                time.sleep(1.0)

        return evaluated_vacancies

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _request_ai_with_retry(self, prompt: str, max_retries: int | None = None) -> list[dict]:
        """
        Retries through the model fallback chain.
        Switches model immediately on 429 rate limits, fatal errors, and parse failures.
        """
        local_chain: list[str] | None = (
            list(self._fallback_chain_original)
            if self._fallback_chain_original is not None
            else None
        )
        current_model = self.model

        if max_retries is None:
            max_retries = max(len(local_chain) + 2 if local_chain else 5, 8)

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
                    "timeout": 45,
                }
                # Native OpenRouter server-side fallback array (OpenRouter limit: max 3 total models)
                if self.provider == "OpenRouter" and local_chain:
                    server_fallbacks = [m for m in local_chain if m != current_model][:2]
                    if server_fallbacks:
                        kwargs["extra_body"] = {"models": server_fallbacks}

                response = self.client.chat.completions.create(**kwargs)

                raw_content = response.choices[0].message.content or ""

                preview = raw_content[:200].replace("\n", " ")
                safe_log(f"    [RAW] Model reply preview: {preview}")

                results = self._extract_results(raw_content)
                safe_log(f"    [PARSE] Extracted {len(results)} items from response")

                if len(results) == 0:
                    raise ValueError("ParseError: Model returned 0 valid JSON items")

                # Persist whichever model succeeded
                self.model = current_model
                return results

            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()

                is_fatal = any(sig in err_str for sig in FATAL_ERROR_SIGNALS)
                is_rate_limit = (
                    "429" in err_str
                    or "rate_limit" in err_str
                    or "quota" in err_str.lower()
                    or "temporarily rate-limited" in err_str
                )
                is_parse_error = "parseerror" in err_str.lower()

                # On fatal error or rate limit, switch model IMMEDIATELY (no sleep on dead model)
                if (is_fatal or is_rate_limit or is_parse_error) and local_chain:
                    if current_model in local_chain:
                        local_chain.remove(current_model)

                    if local_chain:
                        old_model = current_model
                        current_model = local_chain[0]
                        reason = "Rate limited (429)" if is_rate_limit else "Fatal error" if is_fatal else "Parse error"
                        safe_log(f"    [FAIL-FAST] {reason} on {old_model} → switching to {current_model}")
                        self.model = current_model
                        if self.on_model_switch:
                            self.on_model_switch(old_model, current_model)
                        continue
                    else:
                        safe_log("    [ERROR] Все резервные модели исчерпаны.")

                # If no fallback chain available, wait briefly
                wait = min(attempt * 2.0, 8.0)
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

        # ── Step 0: Strip reasoning/thinking tags ──
        clean_text = re.sub(r"<think>.*?</think>", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"<thinking>.*?</thinking>", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"<reasoning>.*?</reasoning>", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = clean_text.strip()

        # ── Step 1: Strip markdown code fences ──
        if "```json" in clean_text:
            clean_text = clean_text.split("```json", 1)[1]
            if "```" in clean_text:
                clean_text = clean_text.split("```", 1)[0]
        elif "```" in clean_text:
            parts = clean_text.split("```")
            clean_text = parts[1] if len(parts) >= 3 else clean_text.replace("```", "")
        clean_text = clean_text.strip()

        # ── Step 2: Direct JSON parse ──
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

        # ── Step 3: Find outermost JSON array or object ──
        bracket_match = re.search(r"\[[\s\S]*\]", clean_text)
        if bracket_match:
            try:
                parsed = json.loads(bracket_match.group(0), strict=False)
                if isinstance(parsed, list):
                    return [p for p in parsed if isinstance(p, dict)]
            except Exception:
                pass

        brace_match = re.search(r"\{[\s\S]*\}", clean_text)
        if brace_match:
            try:
                parsed = json.loads(brace_match.group(0), strict=False)
                if isinstance(parsed, dict):
                    for key in ("results", "data", "vacancies", "items"):
                        if isinstance(parsed.get(key), list):
                            return [p for p in parsed[key] if isinstance(p, dict)]
            except Exception:
                pass

        # ── Step 4: Extract item by item with regex ──
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

            try:
                tid = int(match.group(1))
                item_dict: dict = {"temp_id": tid}

                for field in ["role_match", "level_match", "tech_match", "experience_match"]:
                    m = re.search(rf'"{field}"\s*:\s*(\d+)', chunk)
                    if m:
                        item_dict[field] = int(m.group(1))

                for field in ["TechStack", "AiSummary", "ExtractedExperience",
                               "detected_role", "detected_level", "critical_reason"]:
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

            # Preserve scraper tags if AI returned empty / generic
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
            if (not current_exp or current_exp in ("Смотреть в описании", "Не указано", "не указан")) and extracted_exp and extracted_exp not in ("Не указано", "-"):
                updated["RequiredExperience"] = extracted_exp

            updated.pop("_temp_id", None)
            updated.pop("DescriptionSnippet", None)
            merged.append(updated)

        return merged

    @classmethod
    def _extract_fallback_tech(cls, title: str, desc: str) -> str:
        known_techs = [
            "C#", ".NET", ".NET Core", "ASP.NET", "Entity Framework", "SQL", "PostgreSQL",
            "MySQL", "Python", "Django", "FastAPI", "Flask", "JavaScript", "TypeScript",
            "React", "Vue", "Angular", "Node.js", "Java", "Spring", "Kotlin", "Go",
            "Golang", "Rust", "C++", "Docker", "Kubernetes", "AWS", "Azure", "GCP",
            "Git", "REST API", "GraphQL", "Redis", "MongoDB", "RabbitMQ", "Kafka",
            "HTML", "CSS", "Tailwind", "Bootstrap", "Linux", "CI/CD", "Creatio", "Umbraco", "QA"
        ]
        combined = f"{title} {desc}".lower()
        found = []
        for tech in known_techs:
            t_low = tech.lower()
            if t_low in combined:
                found.append(tech)
        if found:
            return ", ".join(found[:5])
        return "C#, .NET" if ("c#" in title.lower() or ".net" in title.lower()) else "IT Стек"

    @classmethod
    def _fallback_vacancy(cls, vacancy: Vacancy) -> Vacancy:
        fallback = dict(vacancy)
        title = fallback.get("Title", "")
        desc = fallback.get("DescriptionSnippet", "")
        tech = cls._extract_fallback_tech(title, desc)
        fallback.update({
            "TechStack": tech,
            "AiSummary": f"Позиція «{title}». Основний стек: {tech}.",
            "AiMatchScore": 55,
        })
        fallback.pop("_temp_id", None)
        fallback.pop("DescriptionSnippet", None)
        return fallback
