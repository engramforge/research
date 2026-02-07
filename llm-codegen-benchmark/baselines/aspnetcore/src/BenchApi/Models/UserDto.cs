using System.ComponentModel.DataAnnotations;

namespace BenchApi.Models;

public record CreateUserRequest(
    [Required][EmailAddress] string Email,
    [Required][StringLength(100, MinimumLength = 1)] string Name,
    [Required][StringLength(100, MinimumLength = 8)] string Password
);

public record UserResponse(
    long Id,
    string Email,
    string Name
)
{
    public static UserResponse FromUser(User user) =>
        new(user.Id, user.Email, user.Name);
}
