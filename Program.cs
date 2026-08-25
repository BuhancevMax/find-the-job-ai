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
builder.Services.AddHttpClient("", client =>
{
    client.Timeout = TimeSpan.FromMinutes(10);
});
builder.Services.AddDbContext<AppDbContext>();
builder.Services.AddHttpClient<IParsingBackendClient, ParsingBackendClient>();
builder.Services.AddScoped<IVacancyService, VacancyService>();
var app = builder.Build();

// Auto-migration for SQLite without EF Tools
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    db.Database.EnsureCreated();
    
    try
    {
        // Check if Source column exists, if not, add it
        db.Database.ExecuteSqlRaw("ALTER TABLE Vacancies ADD COLUMN Source TEXT DEFAULT ''");
    }
    catch
    {
        // Column likely already exists, ignore
    }
}

// Configure the HTTP request pipeline.
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    // The default HSTS value is 30 days. You may want to change this for production scenarios, see https://aka.ms/aspnetcore-hsts.
    app.UseHsts();
}

app.UseHttpsRedirection();


app.UseAntiforgery();

app.MapStaticAssets();
app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

app.Run();