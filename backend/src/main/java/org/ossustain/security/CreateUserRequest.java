package org.ossustain.security;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CreateUserRequest(@NotBlank @Size(min = 3, max = 100) String username,
        @NotBlank String role) { }
