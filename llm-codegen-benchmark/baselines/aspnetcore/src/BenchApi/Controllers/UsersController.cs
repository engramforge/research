using BenchApi.Models;
using BenchApi.Services;
using Microsoft.AspNetCore.Mvc;

namespace BenchApi.Controllers;

[ApiController]
[Route("api/v1/users")]
public class UsersController : ControllerBase
{
    private readonly IUserService _userService;

    public UsersController(IUserService userService)
    {
        _userService = userService;
    }

    [HttpPost]
    public ActionResult<UserResponse> CreateUser([FromBody] CreateUserRequest request)
    {
        if (!ModelState.IsValid)
        {
            return BadRequest(ModelState);
        }

        try
        {
            var user = _userService.CreateUser(request);
            return CreatedAtAction(
                nameof(GetUser),
                new { id = user.Id },
                UserResponse.FromUser(user));
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    [HttpGet("{id}")]
    public ActionResult<UserResponse> GetUser(long id)
    {
        var user = _userService.FindById(id);
        if (user is null)
        {
            return NotFound();
        }
        return Ok(UserResponse.FromUser(user));
    }
}
