using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Runtime.CompilerServices;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Configuration;

namespace BlazorApp1.Services;

public class StreamEventMessage
{
    public string Type { get; set; } = string.Empty;
    public int Percent { get; set; }
    public string Message { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public int Count { get; set; }
    public List<Models.Vacancy> Data { get; set; } = [];
}

public interface IParsingBackendClient
{
    IAsyncEnumerable<StreamEventMessage> ParseVacanciesStreamAsync(
        List<string> targetPlatforms, 
        string apiKey, 
        string keyword, 
        string targetRole, 
        string targetExp, 
        string language, 
        string salaryExpectations,
        string workFormat,
        string englishLevel,
        string employmentType,
        CancellationToken ct = default);

    Task<string> ChatAsync(
        string apiKey,
        Models.Vacancy vacancy,
        List<ChatMessage> history,
        string message,
        CancellationToken ct = default);
}

public record ChatMessage(string Role, string Content);

public class ParsingBackendClient(HttpClient httpClient, IConfiguration configuration) : IParsingBackendClient
{
    private readonly HttpClient _httpClient = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
    private readonly string _backendUrl = configuration["PythonBackendUrl"] ?? "http://127.0.0.1:8000";

    public async IAsyncEnumerable<StreamEventMessage> ParseVacanciesStreamAsync(
        List<string> targetPlatforms, 
        string apiKey, 
        string keyword, 
        string targetRole, 
        string targetExp, 
        string language, 
        string salaryExpectations,
        string workFormat,
        string englishLevel,
        string employmentType,
        [EnumeratorCancellation] CancellationToken ct = default)
    {
        string requestUrl = $"{_backendUrl}/parse-stream";

        var payload = new
        {
            api_key = apiKey,
            keyword = keyword,
            target_role = targetRole,
            target_exp = targetExp,
            language = language,
            platforms = targetPlatforms,
            salary_expectations = salaryExpectations,
            work_format = workFormat,
            english_level = englishLevel,
            employment_type = employmentType
        };

        var jsonBody = JsonSerializer.Serialize(payload);
        using var content = new StringContent(jsonBody, Encoding.UTF8, "application/json");

        using var request = new HttpRequestMessage(HttpMethod.Post, requestUrl)
        {
            Content = content
        };

        using var response = await _httpClient.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();

        using var stream = await response.Content.ReadAsStreamAsync(ct).ConfigureAwait(false);
        using var reader = new StreamReader(stream, Encoding.UTF8, false, 1024, leaveOpen: true);

        var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };

        while (!reader.EndOfStream && !ct.IsCancellationRequested)
        {
            var line = await reader.ReadLineAsync(ct).ConfigureAwait(false);
            if (string.IsNullOrWhiteSpace(line)) continue;

            StreamEventMessage? streamEvent = null;
            try
            {
                streamEvent = JsonSerializer.Deserialize<StreamEventMessage>(line, options);
            }
            catch (JsonException)
            {
                // Log exception in a real app, silently ignore corrupted stream chunks here
            }

            if (streamEvent != null)
            {
                yield return streamEvent;
            }
        }
    }

    public async Task<string> ChatAsync(
        string apiKey,
        Models.Vacancy vacancy,
        List<ChatMessage> history,
        string message,
        CancellationToken ct = default)
    {
        string requestUrl = $"{_backendUrl}/chat";

        // Serialize vacancy to a plain dictionary
        var vacancyDict = new Dictionary<string, object?>
        {
            ["Title"]              = vacancy.Title,
            ["Company"]            = vacancy.Company,
            ["Url"]                = vacancy.Url,
            ["Source"]             = vacancy.Source,
            ["RequiredExperience"] = vacancy.RequiredExperience,
            ["TechStack"]          = vacancy.TechStack,
            ["AiSummary"]          = vacancy.AiSummary,
        };

        var payload = new
        {
            api_key = apiKey,
            vacancy = vacancyDict,
            history = history.Select(m => new { role = m.Role, content = m.Content }).ToList(),
            message = message
        };

        var jsonBody = JsonSerializer.Serialize(payload);
        using var content = new StringContent(jsonBody, Encoding.UTF8, "application/json");

        var response = await _httpClient.PostAsync(requestUrl, content, ct).ConfigureAwait(false);
        var responseBody = await response.Content.ReadAsStringAsync(ct).ConfigureAwait(false);

        if (!response.IsSuccessStatusCode)
            return $"Ошибка сервера ({response.StatusCode}).";

        var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
        using var doc = JsonDocument.Parse(responseBody);
        return doc.RootElement.TryGetProperty("reply", out var replyEl)
            ? replyEl.GetString() ?? "Нет ответа."
            : "Нет ответа.";
    }
}
