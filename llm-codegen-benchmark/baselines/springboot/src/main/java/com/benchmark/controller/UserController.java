package com.benchmark.controller;

import com.benchmark.model.User;
import com.benchmark.model.UserDto;
import com.benchmark.service.UserService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Optional;

@RestController
@RequestMapping("/api/v1/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @PostMapping
    public ResponseEntity<UserDto.Response> createUser(
            @Valid @RequestBody UserDto.Create request) {
        User user = userService.createUser(request);
        return ResponseEntity
                .status(HttpStatus.CREATED)
                .body(UserDto.Response.fromUser(user));
    }

    @GetMapping("/{id}")
    public ResponseEntity<UserDto.Response> getUser(@PathVariable Long id) {
        Optional<User> user = userService.findById(id);
        return user
                .map(u -> ResponseEntity.ok(UserDto.Response.fromUser(u)))
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/health")
    public ResponseEntity<String> health() {
        return ResponseEntity.ok("healthy");
    }
}
