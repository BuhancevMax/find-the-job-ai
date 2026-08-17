#  Find the Job AI

This project is designed to take the manual work out of job hunting. It acts as an automated career assistant by aggregating vacancies from IT platforms and extracting the full, unedited job descriptions. The core feature is its LLM integration: instead of just giving you a list of links, the model analyzes every vacancy against your specific experience and career goals to tell you if it's actually a good match.

##  Key Features

*   **Smart Scoring (via Llama 3.1):** We feed your tech stack, seniority, and experience to the LLM, and it grades every job from 0 to 100 based on how well it actually fits you.
*   **Deep Data Extraction:** Captures the complete, unedited requirements of every vacancy, ensuring the AI evaluates the full context of the job, not just the short preview.
*   **Blacklist & Favorites:** Ability to hide irrelevant vacancies permanently or save them to "Favorites".
*   **Built-in SQLite Caching:** Everything we parse gets stored locally. It makes the app much faster and easier to manage without spamming the job boards with requests.

##  Tech Stack

**Client & Core Logic (.NET):**
*   C# / Blazor Web App
*   Entity Framework Core (Code-First)
*   SQLite

**AI & Scraping (Python):**
*   FastAPI / Uvicorn
*   BeautifulSoup4 / Requests
*   Groq API (Llama-3.1-8b-instant model)

##  Interface
<img width="1889" height="892" alt="Screenshot_1" src="https://github.com/user-attachments/assets/8c5d5db6-f1b5-4fcc-bd8c-b5280557b0dc" />

##  How to Run Locally

### 1. Running the Python Microservice
Python 3.10+ is required for the scraper and AI integration.
```bash
cd PythonScripts
python -m venv .venv
# Activate the virtual environment (Windows):
.venv\Scripts\activate
# Install dependencies:
pip install fastapi uvicorn requests beautifulsoup4 groq
# Start the server:
python -m uvicorn main:app --reload
```
The microservice will start at http://127.0.0.1:8000.

### 2. Running the Blazor Application
Ensure you have the .NET 8 SDK installed.
```bash
# Apply database migrations:
dotnet ef database update
# Run the application:
dotnet run
```
The application will be available at http://localhost:5xxx.

### 3. AI Configuration
1. Get a free API key at https://console.groq.com/keys.
2. In the Blazor UI, paste the key into the API key input field.
3. Select your desired role and current experience level using the dropdown filters.

##  Roadmap
- [ ] Move DB logic from the UI components to a dedicated Service layer (Clean Architecture).
- [ ] Save profile settings and the API key in the browser's Local Storage.
- [ ] Add multi-select filters (checkboxes for specific technologies).
- [ ] Implement a "Top 10 sites" filter and integrate new sources (Work.ua, DOU).
