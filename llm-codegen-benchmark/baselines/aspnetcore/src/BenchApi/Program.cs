using BenchApi.Services;

var builder = WebApplication.CreateBuilder(args);

// Add services
builder.Services.AddControllers();
builder.Services.AddSingleton<IUserService, UserService>();
builder.Services.AddEndpointsApiExplorer();

var app = builder.Build();

// Configure pipeline
app.MapControllers();
app.MapGet("/health", () => Results.Ok(new { status = "healthy" }));

app.Run();

// Make Program class accessible for testing
public partial class Program { }
