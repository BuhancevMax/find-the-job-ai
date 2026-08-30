# -*- coding: utf-8 -*-
"""
Find The Job AI — Скрипт тестирования работоспособности бесплатных LLM моделей на OpenRouter.

Использование:
  cd d:\\Projects\\BlazorApp1\\BlazorApp1\\PythonScripts
  .venv\\Scripts\\python.exe test_models.py --key sk-or-ВАШ_КЛЮЧ
"""

import argparse
import json
import re
import sys
import time
import urllib.request
from openai import OpenAI

from App.config import OPENROUTER_BASE_URL, OPENROUTER_MODEL_FALLBACK_CHAIN

SAMPLE_VACANCIES = [
    {
        "_temp_id": 0,
        "Title": "Middle .NET Developer",
        "RequiredExperience": "2-3 роки",
        "DescriptionSnippet": "C#, .NET 8, ASP.NET Core, Entity Framework, SQL Server, Docker. Досвід від 2 років.",
    },
    {
        "_temp_id": 1,
        "Title": "Senior C# Backend Engineer",
        "RequiredExperience": "5+ років",
        "DescriptionSnippet": "C#, .NET, Microservices, Kubernetes, PostgreSQL, AWS, TeamCity CI/CD.",
    },
    {
        "_temp_id": 2,
        "Title": "Junior / Trainee C# Developer",
        "RequiredExperience": "Без досвіду",
        "DescriptionSnippet": "Шукаємо початківця. Базові знання C#, ООП, розуміння SQL.",
    },
]

PROMPT_TEMPLATE = """Ти — IT HR-аналітик. Оціни наскільки вакансії підходять кандидату.

Профіль кандидата:
- Ціль: Junior/Middle .NET Developer
- Досвід: 1-2 роки
- Стек: C#, .NET, SQL

Для КОЖНОЇ вакансії поверни JSON-об'єкт з полями:
  temp_id (int), role_match (0-100), level_match (0-100), tech_match (0-100), experience_match (0-100),
  critical_mismatch (bool), TechStack (string), AiSummary (string, 1 речення), ExtractedExperience (string)

Поверни ТІЛЬКИ валідний JSON масив (без будь-якого тексту до чи після):
[
  {{"temp_id": 0, "role_match": 85, "level_match": 75, "tech_match": 90, "experience_match": 80, "critical_mismatch": false, "TechStack": "C#, .NET 8, SQL", "AiSummary": "Відмінний збіг за стеком C#.", "ExtractedExperience": "2 роки"}},
  ...
]

ВАКАНСІЇ:
{vacancies_text}
"""


def safe_print(msg: str):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def fetch_live_openrouter_free_models() -> list[str]:
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"User-Agent": "FindTheJobAI/1.0"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
            models = data.get("data", [])
            live = [m["id"] for m in models if ":free" in m.get("id", "")]
            if live:
                preferred = [m for m in OPENROUTER_MODEL_FALLBACK_CHAIN if m in live]
                others = [m for m in live if m not in preferred]
                return preferred + others
    except Exception as e:
        safe_print(f"  [!] Не удалось обновить список с OpenRouter ({e}), используем встроенный список.")
    return list(OPENROUTER_MODEL_FALLBACK_CHAIN)


def extract_json(text: str) -> list[dict]:
    if not text:
        return []
    text = text.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for k in ("results", "data", "vacancies", "items"):
                if isinstance(parsed.get(k), list):
                    return parsed[k]
    except Exception:
        pass

    array_match = re.search(r"\[.*\]", text, re.DOTALL)
    if array_match:
        try:
            parsed = json.loads(array_match.group(0))
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

    items = []
    for m in re.finditer(r'\{[^{}]*"temp_id"\s*:\s*\d+[^{}]*\}', text, re.DOTALL):
        try:
            items.append(json.loads(m.group(0)))
        except Exception:
            pass
    return items


def test_single_model(client: OpenAI, model: str, batch: list[dict], fallback_list: list[str]) -> dict:
    vacancies_text = "\n".join(
        f"[ID: {v['_temp_id']}] {v['Title']} | Опыт: {v['RequiredExperience']} | {v['DescriptionSnippet']}"
        for v in batch
    )
    prompt = PROMPT_TEMPLATE.format(vacancies_text=vacancies_text)

    t0 = time.time()
    try:
        kwargs: dict = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.05,
            "max_tokens": 2048,
            "timeout": 35,
        }
        fallbacks = [m for m in fallback_list if m != model][:2]
        if fallbacks:
            kwargs["extra_body"] = {"models": fallbacks}

        resp = client.chat.completions.create(**kwargs)
        elapsed = time.time() - t0
        raw = resp.choices[0].message.content or ""
        results = extract_json(raw)
        valid_items = [r for r in results if isinstance(r, dict) and "temp_id" in r]
        ok = len(valid_items) == len(batch)

        sample_summary = ""
        if valid_items:
            sample_summary = str(valid_items[0].get("AiSummary", ""))[:80]

        return {
            "ok": ok,
            "parsed": len(valid_items),
            "total": len(batch),
            "elapsed": elapsed,
            "actual_model": resp.model,
            "error": "" if ok else f"Распознано {len(valid_items)}/{len(batch)} объектов",
            "preview": sample_summary or raw[:100].replace("\n", " "),
        }
    except Exception as exc:
        elapsed = time.time() - t0
        err_msg = str(exc)
        if "429" in err_msg or "rate_limit" in err_msg.lower():
            status_err = "429 Rate Limit"
        elif "404" in err_msg or "not found" in err_msg.lower():
            status_err = "404 Not Found"
        elif "401" in err_msg or "invalid_api_key" in err_msg.lower():
            status_err = "401 Invalid API Key"
        else:
            status_err = err_msg[:90]

        return {
            "ok": False,
            "parsed": 0,
            "total": len(batch),
            "elapsed": elapsed,
            "actual_model": model,
            "error": status_err,
            "preview": "",
        }


def main():
    parser = argparse.ArgumentParser(description="Тестирование бесплатных OpenRouter моделей")
    parser.add_argument("--key", type=str, default="", help="OpenRouter API ключ (sk-or-...)")
    args = parser.parse_args()

    key = (args.key or "").strip()
    if not key:
        safe_print("=" * 75)
        safe_print("  ОШИБКА: API-ключ OpenRouter не указан!")
        safe_print("=" * 75)
        safe_print("Запустите скрипт с передачей ключа:")
        safe_print("  .venv\\Scripts\\python.exe test_models.py --key sk-or-ВАШ_КЛЮЧ")
        sys.exit(1)

    safe_print("\n[1/2] Запрос актуального каталога бесплатных моделей OpenRouter...")
    models_to_test = fetch_live_openrouter_free_models()
    safe_print(f"      Найдено бесплатных моделей: {len(models_to_test)}")

    safe_print(f"\n[2/2] Тестирование моделей OpenRouter ({len(models_to_test)} шт.)...")
    safe_print("=" * 80)
    safe_print(f" {'Статус':^8} | {'Время':^8} | {'Модель':<42} | Инфо")
    safe_print("=" * 80)

    client = OpenAI(api_key=key, base_url=OPENROUTER_BASE_URL)
    results = []

    for model in models_to_test:
        res = test_single_model(client, model, SAMPLE_VACANCIES, models_to_test)
        res["model"] = model
        results.append(res)

        if res["ok"]:
            status_tag = "[ OK ]"
            info = f"'{res['preview']}'" if res["preview"] else "JSON корректен"
        else:
            status_tag = "[FAIL]"
            info = res["error"]

        safe_print(f" {status_tag} | {res['elapsed']:>6.2f}s | {model:<42} | {info}")
        time.sleep(1.5)

    safe_print("\n" + "=" * 80)
    safe_print("  ИТОГОВЫЙ РЕЙТИНГ РАБОЧИХ МОДЕЛЕЙ (по скорости):")
    safe_print("=" * 80)

    working = [r for r in results if r["ok"]]
    working.sort(key=lambda x: x["elapsed"])

    if working:
        for idx, r in enumerate(working, 1):
            safe_print(f"  #{idx:02d} | {r['elapsed']:>5.2f}s | {r['model']}")

        safe_print("\n  Рекомендуемый список для config.py:")
        safe_print("  OPENROUTER_MODEL_FALLBACK_CHAIN = [")
        for r in working:
            safe_print(f'      "{r["model"]}",')
        safe_print("  ]")
    else:
        safe_print("  [!] Ни одна модель не ответила успешно. Проверьте правильность API ключа.")

    safe_print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
