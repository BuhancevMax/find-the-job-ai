using BlazorApp1.Models;
using Microsoft.EntityFrameworkCore;

namespace BlazorApp1.Data;

public class AppDbContext : DbContext
{
    public DbSet<Vacancy> Vacancies { get; set; }

    protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
    {
        // Пока используем локальный файл SQLite
        optionsBuilder.UseSqlite("Data Source=vacancies.db");
    }
}