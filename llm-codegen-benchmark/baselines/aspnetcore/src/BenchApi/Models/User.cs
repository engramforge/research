namespace BenchApi.Models;

public class User
{
    public long Id { get; set; }
    public required string Email { get; set; }
    public required string Name { get; set; }
    public required string HashedPassword { get; set; }
}
