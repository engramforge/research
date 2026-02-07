using System.Collections.Concurrent;
using BenchApi.Models;

namespace BenchApi.Services;

public interface IUserService
{
    User CreateUser(CreateUserRequest request);
    User? FindById(long id);
}

public class UserService : IUserService
{
    private readonly ConcurrentDictionary<long, User> _usersDb = new();
    private long _nextId = 1;

    public User CreateUser(CreateUserRequest request)
    {
        // Check for duplicate email
        if (_usersDb.Values.Any(u => u.Email == request.Email))
        {
            throw new ArgumentException("Email already registered");
        }

        var id = Interlocked.Increment(ref _nextId) - 1;
        var user = new User
        {
            Id = id,
            Email = request.Email,
            Name = request.Name,
            HashedPassword = $"hashed_{request.Password}"
        };

        _usersDb[id] = user;
        return user;
    }

    public User? FindById(long id)
    {
        return _usersDb.GetValueOrDefault(id);
    }
}
