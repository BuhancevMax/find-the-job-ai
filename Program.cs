using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using BlazorApp1.Components;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.EntityFrameworkCore;
using BlazorApp1.Data;
using BlazorApp1.Services;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var builder = WebApplication.CreateBuilder(args);

// Configure persistent Data Protection keys to prevent CryptographicException on restarts/standalone
var dataProtectionPath = Path.Combine(
    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
    "FindTheJobAI", "DataProtection-Keys");
Directory.CreateDirectory(dataProtectionPath);

builder.Services.AddDataProtection()
    .PersistKeysToFileSystem(new DirectoryInfo(dataProtectionPath))
    .SetApplicationName("FindTheJobAI");

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

// Auto-start bundled backend process if present in standalone mode
var baseDir = AppContext.BaseDirectory;
string[] candidatePaths = [
    Path.Combine(baseDir, "backend", "backend.exe"),
    Path.Combine(baseDir, "PythonScripts", "dist", "backend", "backend.exe"),
    Path.Combine(baseDir, "..", "PythonScripts", "dist", "backend", "backend.exe")
];

string? foundBackendExe = candidatePaths.FirstOrDefault(File.Exists);
Process? backendProcess = null;

if (foundBackendExe != null)
{
    try
    {
        backendProcess = Process.Start(new ProcessStartInfo
        {
            FileName = foundBackendExe,
            WorkingDirectory = Path.GetDirectoryName(foundBackendExe)!,
            UseShellExecute = false,
            CreateNoWindow = true,
        });
        Console.WriteLine($"[INFO] Python AI backend started (PID: {backendProcess?.Id})");
    }
    catch (Exception ex)
    {
        Console.WriteLine($"[WARN] Could not auto-start backend: {ex.Message}");
    }
}

var lifetime = app.Services.GetRequiredService<IHostApplicationLifetime>();
lifetime.ApplicationStopping.Register(() =>
{
    if (backendProcess != null && !backendProcess.HasExited)
    {
        try { backendProcess.Kill(entireProcessTree: true); } catch { }
    }
});

lifetime.ApplicationStarted.Register(() =>
{
    if (!app.Environment.IsDevelopment())
    {
        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = "http://localhost:5104",
                UseShellExecute = true
            });
        }
        catch { }
    }
});

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

app.UseAntiforgery();
app.MapStaticAssets();
app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

app.Run();