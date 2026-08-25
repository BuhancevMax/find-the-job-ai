import json
import re
import threading
import time
from collections.abc import Callable

from openai import OpenAI

from App.AI.prompt_loader import load_prompt
from App.config import (
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_GROQ_MODEL,
    DEFAULT_OPENROUTER_MODEL,
    OPENROUTER_MODEL_FALLBACK_CHAIN,
    DEEPSEEK_BASE_URL,
    EXPERIENCE_WEIGHT,
    GROQ_BASE_URL,
    LEVEL_WEIGHT,
    OPENROUTER_BASE_URL,
    ROLE_WEIGHT,
    TECH_WEIGHT,
)
from App.models import Vacancy, JobCriteria

BATCH_SIZE = 7


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
    Evaluates vacancies in batches via an OpenAI-compatible LLM.
    For OpenRouter: auto-switches to slower fallback model on 429 or parse error.
    """

    def __init__(self, api_key: str, model: str | None = None):
        if not api_key:
            raise ValueError("API key не указан.")

        self.api_key = api_key.strip()
        # Callback fired when a model switch happens (streaming mode)
        self.on_model_switch: Callable[[str, str], None] | None = None

        if self.api_key.startswith("gsk_"):
            self.base_url = GROQ_BASE_URL
            self.model = model or DEFAULT_GROQ_MODEL
            self.provider = "Groq"
            # Immutable original chain — used to restore per-call
            self._fallback_chain_original: list[str] | None = None
        elif self.api_key.startswith("sk-or-"):
            self.base_url = OPENROUTER_BASE_URL
            self.model = model or DEFAULT_OPENROUTER_MODEL
            self.provider = "OpenRouter"
            self._fallback_chain_original = list(OPENROUTER_MODEL_FALLBACK_CHAIN)
        else:
            self.base_url = DEEPSEEK_BASE_URL
            self.model = model or DEFAULT_DEEPSEEK_MODEL
            self.provider = "DeepSeek"
            self._fallback_chain_original = None

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
          - every ~2s while the AI is thinking (smooth crawl)
          - at end of each batch (pct_end)
        """
        if not vacancies:
            return []

        total = len(vacancies)
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        evaluated_vacancies: list[Vacancy] = []

        safe_log(f"[AI] Анализируем {total} вакансий через {self.provider} ({self.model})...")

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
                    on_progress(tick_pct, f"ИИ думает... батч {batch_num}/{total_batches}")

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

    def _request_ai_with_retry(self, prompt: str, max_retries: int = 4) -> list[dict]:
        """
        Retries up to max_retries times.
        Fix #3: uses a LOCAL copy of the fallback chain per call so that
        exhausting models in one batch does NOT affect the next batch.
        Fix #6: adds timeout=120 to prevent indefinite hangs.
        """
        # Fresh local chain per call — never mutates self._fallback_chain_original
        local_chain: list[str] | None = (
            list(self._fallback_chain_original)
            if self._fallback_chain_original is not None
            else None
        )
        current_model = self.model  # local copy; we update self.model only on switch

        last_exc: Exception | None = None
        attempts_on_current = 0
        MAX_ATTEMPTS_PER_MODEL = 2

        attempt = 0
        while attempt < max_retries:
            attempt += 1
            try:
                response = self.client.chat.completions.create(
                    model=current_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.05,
                    max_tokens=4096,
                    timeout=120,  # Fix #6: prevent indefinite hangs
                )

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
                err_str = str(exc)
                is_rate_limit = (
                    "429" in err_str
                    or "rate_limit" in err_str.lower()
                    or "quota" in err_str.lower()
                )
                is_parse_error = "ParseError" in err_str

                if (is_rate_limit or is_parse_error) and local_chain:
                    attempts_on_current += 1
                    if attempts_on_current >= MAX_ATTEMPTS_PER_MODEL:
                        if current_model in local_chain:
                            local_chain.remove(current_model)

                        if local_chain:
                            old_model = current_model
                            current_model = local_chain[0]
                            attempts_on_current = 0
                            safe_log(f"    [MODEL SWITCH] {old_model} -> {current_model}")
                            # Notify UI and update instance model
                            self.model = current_model
                            if self.on_model_switch:
                                self.on_model_switch(old_model, current_model)
                            continue
                        else:
                            safe_log("    [ERROR] Все резервные модели исчерпаны.")

                wait_match = re.search(r"try again in ([\d\.]+)s", err_str, re.IGNORECASE)
                if wait_match:
                    try:
                        wait = min(float(wait_match.group(1)) + 1.0, 15.0)
                    except ValueError:
                        wait = attempt * 3.0
                else:
                    wait = attempt * 3.0

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
        return clean[:350]

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
