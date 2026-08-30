# 🚀 Find the Job AI

**Find the Job AI** is an intelligent career assistant and job aggregator designed to automate the search and evaluation of IT vacancies.

The application aggregates vacancies from multiple job boards in parallel, enriches descriptions and requirements, and runs deep LLM analysis matching each job against your specific tech stack, experience level, salary expectations, and working conditions with a deterministic fit score (0–100%).

---

## ✨ Key Features

* **Multi-Platform Scraping**: Parallel aggregation from **Djinni**, **Work.ua**, **Robota.ua**, and **DOU.ua** with multi-filter queries, description search (`descr=1`), and soft fallbacks.
* **Zero-Cost AI Matching**: Powered by **OpenRouter Free Tier (`:free`)** with automatic multi-model failover (`minimax-m3:free`, `dots-3-note-preview:free`, `ling-3.0-flash-fin:free`, `openrouter/free`).
* **Deterministic Scoring (0–100%)**: Weighted scoring assessing role fit (25%), seniority (25%), tech stack match (30%), and experience requirements (20%).
* **Tinder Swipe Mode**: Interactive 2-layer card deck with animated swiping, stamp feedback (**«ЛАЙК»** / **«БЛОК»**), and smooth deck promotion.
* **Vacancy-Scoped AI Assistant**: Dedicated conversational chat for every vacancy with dual-layer prompt-injection guardrails.
* **Strict Experience Normalization**: Automatic cleaning of complex Ukrainian, English, and Russian experience phrases into unified formats (`1-3 года`, `от 1 года`, `5+ лет`, `без опыта`, `в описании`).
* **Local Persistence & Cache**: SQLite database with Entity Framework Core, LocalStorage settings persistence, and fast filtering (All / Favorites / Blacklist).

---

## 🛠️ Tech Stack

### Frontend & Core Service (.NET 9)
* **Framework**: ASP.NET Core Blazor Web App (.NET 9)
* **ORM & Database**: Entity Framework Core, SQLite
* **Styling**: Vanilla CSS3 with glassmorphism, responsive spring animations, light/dark theme variables

### Backend & AI Microservice (Python)
* **Framework**: FastAPI, Uvicorn
* **Scraping Engine**: BeautifulSoup4, CloudScraper, Requests, ThreadPoolExecutor
* **LLM Engine**: OpenAI SDK with OpenRouter Free API router

---

## 🚀 How to Run Locally

### Prerequisites
* **.NET 9 SDK**
* **Python 3.10+**
* Free API key from [openrouter.ai/keys](https://openrouter.ai/keys) (no credit card required)

---

### 1. Start Python Backend

```bash
cd PythonScripts
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```
Backend will start at `http://127.0.0.1:8000`.

---

### 2. Start Blazor Application

In the project root directory:

```bash
dotnet run
```
Blazor frontend will start at `http://localhost:5104` (or `https://localhost:7123`).

---

### 3. Usage

1. Open `http://localhost:5104` in your browser.
2. Enter your OpenRouter API key (`sk-or-v1-...`).
3. Select your target tech stack chips (e.g., `JavaScript`, `React`, `Python`, `C#`).
4. Set role, experience, target language, and salary expectations.
5. Click **«Найти вакансии»** to stream real-time results and AI insights!
