using System;
using System.Collections.Generic;

namespace BlazorApp1.Services;

public interface ILocalizationService
{
    string CurrentLanguage { get; set; }
    string T(string key);
    event Action? OnLanguageChanged;
}

public class LocalizationService : ILocalizationService
{
    private string _currentLanguage = "uk"; // Default to Ukrainian

    public string CurrentLanguage
    {
        get => _currentLanguage;
        set
        {
            if (_currentLanguage != value)
            {
                _currentLanguage = value == "en" ? "en" : "uk";
                OnLanguageChanged?.Invoke();
            }
        }
    }

    public event Action? OnLanguageChanged;

    public string T(string key)
    {
        if (Translations.TryGetValue(key, out var dict))
        {
            if (dict.TryGetValue(_currentLanguage, out var val))
                return val;
            if (dict.TryGetValue("uk", out var fallback))
                return fallback;
        }
        return key;
    }

    private static readonly Dictionary<string, Dictionary<string, string>> Translations = new(StringComparer.OrdinalIgnoreCase)
    {
        // ── Header & App Brand ──
        ["AppTitle"] = new() { ["uk"] = "Find the Job AI", ["en"] = "Find the Job AI" },
        ["AppSubtitle"] = new() { ["uk"] = "Розумний агрегатор IT-вакансій з ШІ-аналізом", ["en"] = "Intelligent IT job aggregator with AI analysis" },
        ["BetaBadge"] = new() { ["uk"] = "Beta v0.9", ["en"] = "Beta v0.9" },
        ["BetaTitle"] = new() { ["uk"] = "Рання бета-версія", ["en"] = "Early Beta Version" },
        ["BetaTooltip"] = new()
        {
            ["uk"] = "Додаток знаходиться на стадії активної розробки. Можливі тимчасові неточності, баги та особливості відображення.",
            ["en"] = "The application is under active development. Minor bugs, display discrepancies, and temporary issues may occur."
        },
        ["ThemeDark"] = new() { ["uk"] = "Темна тема", ["en"] = "Dark theme" },
        ["ThemeLight"] = new() { ["uk"] = "Світла тема", ["en"] = "Light theme" },

        // ── OpenRouter Popover ──
        ["WhyOpenRouter"] = new() { ["uk"] = "Чому OpenRouter?", ["en"] = "Why OpenRouter?" },
        ["OpenRouterTitle"] = new() { ["uk"] = "Безкоштовний ШІ-аналіз", ["en"] = "Free AI Analysis" },
        ["OpenRouterDesc"] = new()
        {
            ["uk"] = "Сервіс надає доступ до провідних безкоштовних (:free) моделей без прив'язки банківських карток та абонплати. Ключ генерується за 1 клік.",
            ["en"] = "The service provides access to leading free (:free) models with zero costs and no credit card required. Generate a key in 1 click."
        },
        ["OpenRouterGetKey"] = new() { ["uk"] = "Отримати ключ:", ["en"] = "Get API Key:" },

        // ── Filter Controls ──
        ["LabelApiKey"] = new() { ["uk"] = "OpenRouter API Ключ", ["en"] = "OpenRouter API Key" },
        ["LabelRole"] = new() { ["uk"] = "Посада", ["en"] = "Target Role" },
        ["LabelExperience"] = new() { ["uk"] = "Досвід", ["en"] = "Experience" },
        ["LabelAiLanguage"] = new() { ["uk"] = "Мова ШІ", ["en"] = "AI Language" },
        ["LabelFormat"] = new() { ["uk"] = "Формат", ["en"] = "Work Format" },
        ["LabelSalary"] = new() { ["uk"] = "Зарплата ($)", ["en"] = "Salary ($)" },
        ["LabelPlatforms"] = new() { ["uk"] = "Платформи:", ["en"] = "Platforms:" },
        ["BtnSearch"] = new() { ["uk"] = "Знайти вакансії", ["en"] = "Find Vacancies" },
        ["BtnSearching"] = new() { ["uk"] = "Пошук...", ["en"] = "Searching..." },

        // ── Dropdown Options ──
        ["RoleTrainee"] = new() { ["uk"] = "Trainee / Junior", ["en"] = "Trainee / Junior" },
        ["RoleMiddle"] = new() { ["uk"] = "Middle", ["en"] = "Middle" },
        ["RoleSenior"] = new() { ["uk"] = "Senior", ["en"] = "Senior" },
        ["RoleLead"] = new() { ["uk"] = "Lead / Architect", ["en"] = "Lead / Architect" },
        ["RoleFullstack"] = new() { ["uk"] = "Fullstack", ["en"] = "Fullstack" },
        ["RoleAny"] = new() { ["uk"] = "Будь-яка посада", ["en"] = "Any Role" },

        ["ExpNoExp"] = new() { ["uk"] = "Без комерційного досвіду", ["en"] = "No commercial experience" },
        ["ExpUnder1"] = new() { ["uk"] = "Менше 1 року", ["en"] = "Less than 1 year" },
        ["Exp1to3"] = new() { ["uk"] = "1–3 роки", ["en"] = "1–3 years" },
        ["ExpOver3"] = new() { ["uk"] = "Більше 3 років", ["en"] = "More than 3 years" },

        ["FormatAny"] = new() { ["uk"] = "Будь-який", ["en"] = "Any format" },
        ["FormatRemote"] = new() { ["uk"] = "Віддалено (Remote)", ["en"] = "Remote" },
        ["FormatOffice"] = new() { ["uk"] = "Офіс (Office)", ["en"] = "Office" },
        ["FormatHybrid"] = new() { ["uk"] = "Гібрид (Hybrid)", ["en"] = "Hybrid" },

        // ── Views & Quick Actions ──
        ["ViewAll"] = new() { ["uk"] = "Всі вакансії", ["en"] = "All Vacancies" },
        ["ViewFavorites"] = new() { ["uk"] = "Збережені", ["en"] = "Saved" },
        ["ViewBlacklist"] = new() { ["uk"] = "Чорний список", ["en"] = "Blacklist" },
        ["BtnClearDb"] = new() { ["uk"] = "Очистити БД", ["en"] = "Clear DB" },
        ["BtnClearDbConfirm"] = new() { ["uk"] = "Ви впевнені, що хочете очистити базу даних?", ["en"] = "Are you sure you want to clear the local database?" },

        // ── View Modes ──
        ["ModeTable"] = new() { ["uk"] = "Список", ["en"] = "List" },
        ["ModeTinder"] = new() { ["uk"] = "Tinder режим", ["en"] = "Tinder Mode" },

        // ── Sorting ──
        ["SortTitle"] = new() { ["uk"] = "Посада", ["en"] = "Title" },
        ["SortExperience"] = new() { ["uk"] = "Досвід", ["en"] = "Experience" },
        ["SortScore"] = new() { ["uk"] = "ШІ-відповідність", ["en"] = "AI Fit Score" },

        // ── Cards & Details ──
        ["ScoreLabel"] = new() { ["uk"] = "Збіг", ["en"] = "Match" },
        ["BtnChat"] = new() { ["uk"] = "Чат з ШІ", ["en"] = "AI Chat" },
        ["BtnSave"] = new() { ["uk"] = "Зберегти", ["en"] = "Save" },
        ["BtnSaved"] = new() { ["uk"] = "Збережено", ["en"] = "Saved" },
        ["BtnBlacklist"] = new() { ["uk"] = "В чорний список", ["en"] = "Blacklist" },
        ["BtnRestore"] = new() { ["uk"] = "Відновити", ["en"] = "Restore" },

        // ── Tinder Mode ──
        ["TinderOf"] = new() { ["uk"] = "з", ["en"] = "of" },
        ["TinderStampLike"] = new() { ["uk"] = "ЛАЙК", ["en"] = "LIKE" },
        ["TinderStampNope"] = new() { ["uk"] = "БЛОК", ["en"] = "PASS" },
        ["TinderAllViewed"] = new() { ["uk"] = "Ви переглянули всі вакансії", ["en"] = "You have reviewed all vacancies" },
        ["TinderChangeFilters"] = new() { ["uk"] = "Змініть фільтри або запустіть новий пошук.", ["en"] = "Adjust filters or start a new search." },
        ["TinderBackToList"] = new() { ["uk"] = "Повернутися до списку", ["en"] = "Back to list" },

        // ── Chat Modal ──
        ["ChatSecure"] = new() { ["uk"] = "Захищений чат", ["en"] = "Secure Chat" },
        ["ChatClose"] = new() { ["uk"] = "Закрити чат", ["en"] = "Close chat" },
        ["ChatEmptyTitle"] = new() { ["uk"] = "Задайте будь-яке питання щодо цієї вакансії", ["en"] = "Ask any question about this vacancy" },
        ["ChatEmptyDesc"] = new()
        {
            ["uk"] = "ШІ проаналізує вимоги, оцінить необхідний стек або допоможе скласти супровідний лист.",
            ["en"] = "The AI will analyze the requirements, explain the tech stack, or help tailor your cover letter."
        },
        ["ChatQuickQuestion1"] = new() { ["uk"] = "Які основні вимоги до кандидата?", ["en"] = "What are the core requirements?" },
        ["ChatQuickQuestion2"] = new() { ["uk"] = "Який стек технологій потрібен насамперед?", ["en"] = "Which tech stack skills are top priority?" },
        ["ChatQuickQuestion3"] = new() { ["uk"] = "Чи підійде мій досвід під цю позицію?", ["en"] = "Does my background fit this role?" },
        ["ChatPlaceholder"] = new() { ["uk"] = "Задайте питання про цю вакансію...", ["en"] = "Ask a question about this job..." },
        ["ChatSend"] = new() { ["uk"] = "Надіслати", ["en"] = "Send" },
        ["ChatLimit"] = new() { ["uk"] = "повідомлень у сесії", ["en"] = "messages in session" },

        // ── Blacklist Modal ──
        ["BlacklistTitle"] = new() { ["uk"] = "Чорний список", ["en"] = "Blacklist" },
        ["BlacklistEmpty"] = new() { ["uk"] = "Список порожній", ["en"] = "Blacklist is empty" },

        // ── Empty States & Alerts ──
        ["EmptyVacanciesTitle"] = new() { ["uk"] = "Вакансій не знайдено", ["en"] = "No vacancies found" },
        ["EmptyVacanciesDesc"] = new() { ["uk"] = "Виберіть технології та натисніть «Знайти вакансії».", ["en"] = "Select your technologies and click 'Find Vacancies'." },
        ["EmptyFavoritesTitle"] = new() { ["uk"] = "Немає збережених вакансій", ["en"] = "No saved vacancies" },
        ["EmptyFavoritesDesc"] = new() { ["uk"] = "Натисніть на зірочку або лайкніть вакансію в режимі Tinder.", ["en"] = "Click the bookmark icon or like a vacancy in Tinder mode." },
        ["AnalysisComplete"] = new() { ["uk"] = "Аналіз завершено", ["en"] = "Analysis complete" },
        ["TimeoutError"] = new() { ["uk"] = "Час очікування відповіді сервера вичерпано (таймаут 4 хв).", ["en"] = "Server response timed out (4 min timeout)." },
        ["ConnectionError"] = new() { ["uk"] = "Помилка з'єднання з сервером Python:", ["en"] = "Python backend connection error:" },
    };
}
