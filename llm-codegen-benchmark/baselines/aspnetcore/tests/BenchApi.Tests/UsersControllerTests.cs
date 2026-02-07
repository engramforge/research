using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace BenchApi.Tests;

public class UsersControllerTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public UsersControllerTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task HealthCheck_ReturnsHealthy()
    {
        var response = await _client.GetAsync("/health");
        
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var content = await response.Content.ReadAsStringAsync();
        Assert.Contains("healthy", content);
    }

    [Fact]
    public async Task CreateUser_ValidRequest_ReturnsCreated()
    {
        var request = new
        {
            Email = "test@example.com",
            Name = "Test User",
            Password = "securepassword123"
        };

        var response = await _client.PostAsJsonAsync("/api/v1/users", request);

        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        var content = await response.Content.ReadFromJsonAsync<Dictionary<string, object>>();
        Assert.NotNull(content);
        Assert.Equal("test@example.com", content["email"].ToString());
        Assert.Equal("Test User", content["name"].ToString());
    }

    [Fact]
    public async Task CreateUser_InvalidEmail_ReturnsBadRequest()
    {
        var request = new
        {
            Email = "not-an-email",
            Name = "Test User",
            Password = "securepassword123"
        };

        var response = await _client.PostAsJsonAsync("/api/v1/users", request);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    [Fact]
    public async Task GetUser_NotFound_ReturnsNotFound()
    {
        var response = await _client.GetAsync("/api/v1/users/9999");

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }
}
