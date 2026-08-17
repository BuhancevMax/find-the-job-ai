from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import json
import time
from groq import Groq

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/parse/djinni")
def parse_djinni(api_key: str, keyword: str = "C#", target_role: str = "C# Developer", target_exp: str = "Без опыта"):
    print(f"\n🚀 [START] Парсинг '{keyword}' для профиля: {target_role} ({target_exp})")

    if not api_key:
        return {"status": "error", "message": "API ключ не предоставлен"}

    url = f"https://djinni.co/jobs/?primary_keyword={keyword}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return {"status": "error", "message": f"Сайт заблокировал запрос. Код: {response.status_code}"}

    soup = BeautifulSoup(response.text, 'html.parser')

    jobs_data = []
    script_tags = soup.find_all('script', type='application/ld+json')
    for tag in script_tags:
        try:
            data = json.loads(tag.string)
            if isinstance(data, list):
                jobs_data.extend([item for item in data if item.get('@type') == 'JobPosting'])
            elif isinstance(data, dict) and data.get('@type') == 'JobPosting':
                jobs_data.append(data)
        except Exception as e:
            continue

    print(f"📦 [INFO] Найдено {len(jobs_data)} полных описаний вакансий.")

    if len(jobs_data) == 0:
        return {"status": "error", "message": "Не удалось найти вакансии."}

    client = Groq(api_key=api_key)
    vacancies = []
    batch_size = 5 # Обрабатываем по 5 штук за раз

    # Запускаем цикл по ВСЕМ найденным вакансиям с шагом 5
    for i in range(0, len(jobs_data), batch_size):
        batch = jobs_data[i:i+batch_size]
        batch_vacancies = []

        # --- ОБНОВЛЕННЫЙ УМНЫЙ ПРОМПТ ---
        prompt = f"""
        Ты IT HR-аналитик. Оценивай вакансии ПЕРСОНАЛЬНО для кандидата.
        ПРОФИЛЬ: Ищет: {target_role}, Текущий опыт: {target_exp}
        
        Верни СТРОГО JSON с ключом "results". Для каждой вакансии:
        - "temp_id": (число)
        - "TechStack": (строка, список основных технологий)
        - "AiSummary": (строка, суть работы в 1 коротком предложении СТРОГО НА РУССКОМ ЯЗЫКЕ)
        - "AiMatchScore": (целое число 0-100. Если вакансия не связана с ИТ-разработкой или требуется уровень Senior, а кандидат Junior - ставь 0).
        
        Список вакансий:
        """

        for idx, job in enumerate(batch):
            company_name = job.get("hiringOrganization", {}).get("name", "Неизвестно")
            desc_snippet = job.get("description", "")[:1200].replace('\n', ' ')

            # --- ПРЯМОЙ ПАРСИНГ ОПЫТА БЕЗ ИИ ---
            exp_data = job.get("experienceRequirements", {})
            months = 0
            if isinstance(exp_data, dict):
                months = exp_data.get("monthsOfExperience", 0)

            if months == 0:
                req_exp = "Без опыта"
            elif months < 12:
                req_exp = f"{int(months)} месяцев"
            elif months % 12 == 0:
                y = int(months // 12)
                req_exp = f"{y} год" if y == 1 else f"{y} года" if 1 < y < 5 else f"{y} лет"
            else:
                req_exp = f"{int(months)} месяцев"
            # -----------------------------------

            vac_dict = {
                "_temp_id": idx,
                "Title": job.get("title", "Без названия"),
                "Company": company_name,
                "Url": job.get("url", ""),
                "RequiredExperience": req_exp, # Сразу вставляем готовый опыт
                "TechStack": "",
                "AiSummary": "",
                "AiMatchScore": 0
            }
            batch_vacancies.append(vac_dict)
            prompt += f"\ntemp_id: {idx}\nНазвание: {vac_dict['Title']}\nОписание: {desc_snippet}\n"

        print(f"🧠 [Батч {i//batch_size + 1}] Отправляем {len(batch)} вакансий в ИИ...")

        try:
            start_time = time.time()
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="openai/gpt-oss-20b", # Если менял модель, оставь свое название
                response_format={"type": "json_object"},
                temperature=0.1
            )
            elapsed = round(time.time() - start_time, 2)
            print(f"✨ Успех за {elapsed} сек.")

            response_content = chat_completion.choices[0].message.content
            ai_data = json.loads(response_content)

            # Связываем данные по надежному _temp_id
            for ai_info in ai_data.get("results", []):
                matched_vac = next((v for v in batch_vacancies if v["_temp_id"] == ai_info.get("temp_id")), None)
                if matched_vac:
                    matched_vac["TechStack"] = str(ai_info.get("TechStack", ""))
                    matched_vac["AiSummary"] = str(ai_info.get("AiSummary", ""))
                    score = ai_info.get("AiMatchScore", 0)
                    matched_vac["AiMatchScore"] = int(score) if str(score).isdigit() else 0

        except Exception as e:
            print(f"❌ Ошибка ИИ в батче: {e}")

        # Добавляем готовый батч в общий список, удаляя временный ID
        for v in batch_vacancies:
            del v["_temp_id"]
            vacancies.append(v)

        # Небольшая пауза между батчами, чтобы не разозлить защиту Groq (Rate Limits)
        time.sleep(1.5)

    print(f"🏁 [FINISH] Успешно собрано {len(vacancies)} вакансий!")
    return {"status": "success", "count": len(vacancies), "data": vacancies}