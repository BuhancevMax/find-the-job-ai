using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using BlazorApp1.Models;
using Microsoft.EntityFrameworkCore;
using BlazorApp1.Data;

namespace BlazorApp1.Services;

/// <summary>
/// Interface for vacancy operations.
/// </summary>
public interface IVacancyService
{
    Task<List<Vacancy>> GetVacanciesAsync(bool showOnlySaved, CancellationToken ct = default);
    Task ClearCacheAsync(CancellationToken ct = default);
    Task ToggleSaveAsync(Vacancy vac, CancellationToken ct = default);
    Task RejectVacancyAsync(Vacancy vac, CancellationToken ct = default);
    Task SaveNewVacanciesAsync(IEnumerable<Vacancy> newVacancies, CancellationToken ct = default);
}

/// <summary>
/// Service handling database operations for vacancies.
/// Implements primary constructor syntax and interface segregation.
/// </summary>
public class VacancyService(AppDbContext context) : IVacancyService
{
    private readonly AppDbContext _context = context ?? throw new ArgumentNullException(nameof(context));

    public async Task<List<Vacancy>> GetVacanciesAsync(bool showOnlySaved, CancellationToken ct = default)
    {
        var query = _context.Vacancies.Where(v => !v.IsRejected);

        if (showOnlySaved)
        {
            query = query.Where(v => v.IsSaved);
        }

        return await query.ToListAsync(ct).ConfigureAwait(false);
    }

    public async Task ClearCacheAsync(CancellationToken ct = default)
    {
        var garbage = await _context.Vacancies.Where(v => !v.IsSaved).ToListAsync(ct).ConfigureAwait(false);
        _context.Vacancies.RemoveRange(garbage);
        await _context.SaveChangesAsync(ct).ConfigureAwait(false);
    }

    public async Task ToggleSaveAsync(Vacancy vac, CancellationToken ct = default)
    {
        ArgumentNullException.ThrowIfNull(vac);

        vac.IsSaved = !vac.IsSaved;
        _context.Vacancies.Update(vac);
        await _context.SaveChangesAsync(ct).ConfigureAwait(false);
    }

    public async Task RejectVacancyAsync(Vacancy vac, CancellationToken ct = default)
    {
        ArgumentNullException.ThrowIfNull(vac);

        vac.IsRejected = true;
        vac.IsSaved = false;
        _context.Vacancies.Update(vac);
        await _context.SaveChangesAsync(ct).ConfigureAwait(false);
    }

    public async Task SaveNewVacanciesAsync(IEnumerable<Vacancy> newVacancies, CancellationToken ct = default)
    {
        ArgumentNullException.ThrowIfNull(newVacancies);

        foreach (var vac in newVacancies)
        {
            var existing = await _context.Vacancies.FirstOrDefaultAsync(v => v.Url == vac.Url, ct).ConfigureAwait(false);
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
        await _context.SaveChangesAsync(ct).ConfigureAwait(false);
    }
}