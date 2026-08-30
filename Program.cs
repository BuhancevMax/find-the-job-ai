using System;
using BlazorApp1.Components;
using Microsoft.EntityFrameworkCore;
using BlazorApp1.Data;
using BlazorApp1.Services;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();

builder.Services.AddDbContext<AppDbContext>();

// Register typed ParsingBackendClient with 5-minute timeout for multi-platform streaming
builder.Services.AddHttpClient<IParsingBackendClient, ParsingBackendClient>(client =>
{
    client.Timeout = TimeSpan.FromMinutes(5);
});

builder.Services.AddScoped<IVacancyService, VacancyService>();
builder.Services.AddScoped<ILocalizationService, LocalizationService>();

var app = builder.Build();

// Auto-migration for SQLite on startup
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    db.Database.EnsureCreated();

    try
    {
        db.Database.ExecuteSqlRaw("ALTER TABLE Vacancies ADD COLUMN Source TEXT DEFAULT ''");
    }
    catch
    {
        // Column already exists
    }
}

// Configure the HTTP request pipeline.
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseAntiforgery();
app.MapStaticAssets();
app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

app.Run();