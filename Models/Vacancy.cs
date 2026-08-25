using System;
using System.ComponentModel.DataAnnotations;

namespace BlazorApp1.Models;

public class Vacancy
{
    [Key]
    public int Id { get; set; }
    public string Title { get; set; } = string.Empty;
    public string Company { get; set; } = string.Empty;
    public string SalaryString { get; set; } = string.Empty; // Сырая строка ЗП
    public string Url { get; set; } = string.Empty;
    public string Source { get; set; } = string.Empty; // e.g. "Djinni", "Work.ua", "Djinni, DOU"
    public DateTime PublishedDate { get; set; }
        
    // --- Поля, которые будет генерировать ИИ ---
    public string RequiredExperience { get; set; } = string.Empty; // "1-3 года"
    public string TechStack { get; set; } = string.Empty; // "C#, SQL, Python"
    public string AiSummary { get; set; } = string.Empty; // Выжимка без воды
    public int AiMatchScore { get; set; } // Оценка от 1 до 100
        
    public DateTime ParsedAt { get; set; } = DateTime.Now;
    
    public bool IsSaved { get; set; } = false;
    public bool IsRejected { get; set; } = false;
}