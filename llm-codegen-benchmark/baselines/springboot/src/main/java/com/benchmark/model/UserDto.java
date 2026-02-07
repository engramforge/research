package com.benchmark.model;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public class UserDto {

    public record Create(
            @NotBlank @Email String email,
            @NotBlank @Size(min = 1, max = 100) String name,
            @NotBlank @Size(min = 8, max = 100) String password
    ) {
    }

    public record Response(
            Long id,
            String email,
            String name
    ) {
        public static Response fromUser(User user) {
            return new Response(user.getId(), user.getEmail(), user.getName());
        }
    }
}
