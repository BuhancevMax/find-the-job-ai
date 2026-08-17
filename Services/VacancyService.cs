using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using BlazorApp1.Models;
using Microsoft.EntityFrameworkCore;
using BlazorApp1.Data;

namespace BlazorApp1.Services 
{
    public class VacancyService
    {
        private readonly AppDbContext _context;

        // Внедрение зависимости (Dependency Injection) базы данных
        public VacancyService(AppDbContext context)
        {
            _context = context;
        }

        // 1. Получение вакансий с учетом фильтров
        public async Task<List<Vacancy>> GetVacanciesAsync(bool showOnlySaved)
        {
            var query = _context.Vacancies.Where(v => !v.IsRejected);

            if (showOnlySaved)
            {
                query = query.Where(v => v.IsSaved);
            }

            return await query.ToListAsync();
        }

        // 2. Очистка кэша
        public async Task ClearCacheAsync()
        {
            var garbage = await _context.Vacancies.Where(v => !v.IsSaved).ToListAsync();
            _context.Vacancies.RemoveRange(garbage);
            await _context.SaveChangesAsync();
        }

        // 3. Добавление/Удаление из избранного
        public async Task ToggleSaveAsync(Vacancy vac)
        {
            vac.IsSaved = !vac.IsSaved;
            _context.Vacancies.Update(vac);
            await _context.SaveChangesAsync();
        }

        // 4. Скрытие вакансии (Blacklist)
        public async Task RejectVacancyAsync(Vacancy vac)
        {
            vac.IsRejected = true;
            vac.IsSaved = false;
            _context.Vacancies.Update(vac);
            await _context.SaveChangesAsync();
        }
        // 5. Сохранение новых спарсенных вакансий с проверкой на дубликаты
        public async Task SaveNewVacanciesAsync(IEnumerable<Vacancy> newVacancies)
        {
            foreach (var vac in newVacancies)
            {
                var existing = await _context.Vacancies.FirstOrDefaultAsync(v => v.Url == vac.Url);
                if (existing == null)
                {
                    _context.Vacancies.Add(vac);
                }
                else
                {
                    existing.ParsedAt = DateTime.Now;
                    _context.Vacancies.Update(existing);
                }
            }
            await _context.SaveChangesAsync();
        }
    }
}