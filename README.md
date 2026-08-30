# 🚀 Find the Job AI

<p align="center">
  <img src="https://img.shields.io/badge/.NET-9.0-512BD4?logo=dotnet&logoColor=white" alt=".NET 9" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/OpenRouter-Free%20Tier-6366F1" alt="OpenRouter" />
  <img src="https://img.shields.io/badge/UI-UA%20%7C%20EN-059669" alt="Localization" />
  <img src="https://img.shields.io/badge/Version-v0.9--beta-F59E0B" alt="Beta Version" />
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License" />
</p>

<p align="center">
  <b>🌐 Language / Мова:</b><br/>
  <a href="#-english">🇬🇧 English</a> &nbsp;•&nbsp; <a href="#-українська">🇺🇦 Українська</a>
</p>

---

<a name="-english"></a>
## 🇬🇧 English

### 💡 Overview
**Find the Job AI** is a modern, high-performance IT vacancy aggregator and AI career assistant. It automates finding, filtering, scraping, and deeply evaluating tech jobs across top Ukrainian and international platforms (**Djinni**, **Work.ua**, **DOU.ua**, **Robota.ua**).

Using **OpenRouter's Free Tier LLMs** (:free), the system analyzes job descriptions, normalizes complex experience requirements, extracts actual tech stacks, and scores each vacancy from **0% to 100%** based on your specific profile.

---

### ✨ Key Features

* ⚡ **Parallel Multi-Platform Scraping**: Concurrently queries **Djinni**, **Work.ua**, **DOU.ua**, and **Robota.ua** using multi-parameter URL filters (experience, employment type, remote/office, salary, description search).
* 🤖 **Zero-Cost AI Matching**: Powered by OpenRouter :free models (minimax-m3:free, dots-3-note-preview:free, ling-3.0-flash-fin:free, etc.) with automatic rate-limit failover and dead-model blacklisting per session.
* 🎯 **Deterministic Fit Scoring (0–100%)**: Evaluates role alignment, seniority, tech stack overlap, and experience criteria into a transparent fit percentage.
* 🌐 **Full UA / EN Localization**: Seamless 1-click language switcher ([ UA | EN ]) with persistent LocalStorage saving and synchronized AI response language.
* 🃏 **Interactive Tinder Deck Mode**: Fast swipe deck with tactile like/pass animations, color stamps (**LIKE** / **PASS**), and blacklist recovery modal.
* 💬 **In-App AI Vacancy Assistant**: Dedicated contextual chat for every vacancy to ask questions, check requirements, or draft tailored cover letters.
* 📦 **Local SQLite Cache & NDJSON Streaming**: Real-time streaming progress with sub-second response times and EF Core local database persistence.

---

### 🛠️ Architecture & Tech Stack

* **Frontend**: ASP.NET Core Blazor Interactive Server (.NET 9), Vanilla CSS3 Glassmorphism, Responsive Animations.
* **Backend Microservice**: Python 3.10+, FastAPI, Uvicorn, BeautifulSoup4, CloudScraper, Requests.
* **AI & LLMs**: OpenRouter Free API router with OpenAI Python SDK.
* **Database**: SQLite with Entity Framework Core migrations.

---

### 🚀 Quick Start Guide

#### Prerequisites
* [.NET 9 SDK](https://dotnet.microsoft.com/download/dotnet/9.0)
* [Python 3.10+](https://www.python.org/downloads/)
* Free API key from [openrouter.ai/keys](https://openrouter.ai/keys) (no credit card required)

---

#### 1. Setup & Run Python Microservice

`ash
cd PythonScripts

# Create and activate virtual environment
python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# Install dependencies & run
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
`
Backend will start at http://127.0.0.1:8000.

---

#### 2. Run Blazor Frontend Application

In the repository root:

`ash
dotnet run
`
Open http://localhost:5104 (or https://localhost:7123) in your browser.

---

#### 3. How to Use
1. Enter your OpenRouter API key (sk-or-v1-...).
2. Pick your tech stack chips (e.g. C#, .NET, Python, React, SQL).
3. Select your target seniority, experience, work format, and salary expectations.
4. Click **«Find Vacancies»** (Знайти вакансії) to watch real-time parallel streaming and AI insights!

---

<br/>

<a name="-українська"></a>
## 🇺🇦 Українська

### 💡 Опис проєкту
**Find the Job AI** — це розумний агрегатор IT-вакансій та кар'єрний ШІ-асистент. Додаток автоматизує пошук, збір, нормалізацію та глибоку оцінку вакансій з провідних майданчиків України (**Djinni**, **Work.ua**, **DOU.ua**, **Robota.ua**).

Використовуючи **безкоштовні моделі OpenRouter (:free)**, система аналізує повні тексти вакансій, очищає вимоги до досвіду, виділяє стек технологій та розраховує персональний відсоток відповідності від **0% до 100%**.

---

### ✨ Основні можливості

* ⚡ **Паралельний збір з 4 платформ**: Одночасний пошук на **Djinni**, **Work.ua**, **DOU.ua** та **Robota.ua** з точними фільтрами (досвід, формат, зарплата, тип зайнятості).
* 🤖 **Безкоштовний ШІ-аналіз**: Підтримка провідних :free моделей OpenRouter із автоматичним перемиканням у разі вичерпання лімітів та захистом від зависань.
* 🎯 **Оцінка відповідності (0–100%)**: Зважений аналіз посади, технологічного стеку та досвіду кандидата.
* 🌐 **Повна локалізація (UA / EN)**: Миттєве перемикання мови інтерфейсу [ UA | EN ] зі збереженням у LocalStorage та синхронізацією мови відповідей ШІ.
* 🃏 **Режим Tinder-карток**: Інтерактивний перегляд вакансій свайпами, штампи **ЛАЙК** / **БЛОК** та модальне вікно відновлення з чорного списку.
* 💬 **ШІ-чат з вакансією**: Вбудований діалог для кожної вакансії для аналізу вимог або генерації супровідного листа.
* 📦 **Локальне кешування в SQLite**: Збереження переглянутих та обраних вакансій з миттєвим доступом без повторних запитів.

---

### 🚀 Інструкція із запуску

#### Вимоги
* [.NET 9 SDK](https://dotnet.microsoft.com/download/dotnet/9.0)
* [Python 3.10+](https://www.python.org/downloads/)
* Безкоштовний API ключ з [openrouter.ai/keys](https://openrouter.ai/keys)

---

#### 1. Запуск бекенду (Python)

`ash
cd PythonScripts

python -m venv .venv

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
`

---

#### 2. Запуск фронтенду (Blazor)

У кореневій папці проєкту:

`ash
dotnet run
`
Перейдіть за адресою http://localhost:5104 у вашому браузері.

---

## 📁 Project Structure / Структура проєкту

`	ext
├── Components/
│   ├── Layout/              # Blazor layout templates & styling
│   └── Pages/
│       ├── Home.razor       # Main single-page interactive UI (Filters, Grid, Tinder, Chat)
│       └── Error.razor      # Global error handler
├── Data/
│   └── AppDbContext.cs      # SQLite Entity Framework Core Context
├── Models/
│   └── Vacancy.cs           # C# vacancy entity model
├── Services/
│   ├── LocalizationService.cs  # Typed dictionary localization engine (UA / EN)
│   ├── ParsingBackendClient.cs # HTTP & SSE Streaming client
│   └── VacancyService.cs       # Database persistence & query logic
├── PythonScripts/
│   ├── main.py              # FastAPI application & SSE streaming endpoints
│   ├── requirements.txt     # Python backend dependencies
│   └── App/
│       ├── AI/              # OpenRouter LLM evaluator, prompts & chat service
│       ├── Scrapers/        # Djinni, Work.ua, DOU.ua, Robota.ua scrapers
│       ├── config.py        # Settings & dynamic fallback model registry
│       ├── models.py        # Pydantic data schemas
│       └── utils.py         # Thread-safe logging, token & experience normalizers
├── wwwroot/
│   └── app.css              # Custom responsive stylesheet & glassmorphism theme
├── LICENSE                  # MIT Open Source License
└── README.md                # Project documentation
`

---

## 📄 License / Ліцензія

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
