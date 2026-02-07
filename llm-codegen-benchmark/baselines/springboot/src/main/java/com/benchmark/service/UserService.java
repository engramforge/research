package com.benchmark.service;

import com.benchmark.model.User;
import com.benchmark.model.UserDto;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

@Service
public class UserService {

    private final Map<Long, User> usersDb = new ConcurrentHashMap<>();
    private final AtomicLong nextId = new AtomicLong(1);

    public User createUser(UserDto.Create request) {
        // Check for duplicate email
        boolean emailExists = usersDb.values().stream()
                .anyMatch(u -> u.getEmail().equals(request.email()));
        
        if (emailExists) {
            throw new IllegalArgumentException("Email already registered");
        }

        Long id = nextId.getAndIncrement();
        User user = new User(
                id,
                request.email(),
                request.name(),
                "hashed_" + request.password()
        );
        usersDb.put(id, user);
        return user;
    }

    public Optional<User> findById(Long id) {
        return Optional.ofNullable(usersDb.get(id));
    }
}
