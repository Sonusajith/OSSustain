package org.ossustain.security;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {
    private final AuthService auth;

    public AuthController(AuthService auth) { this.auth = auth; }

    @GetMapping("/csrf")
    public CsrfToken csrf(CsrfToken csrfToken) { return csrfToken; }

    @PostMapping("/login")
    public AuthDtos.UserResponse login(@Valid @RequestBody LoginRequest request,
            HttpServletRequest httpRequest, HttpServletResponse httpResponse) {
        return auth.login(request, httpRequest, httpResponse);
    }

    @GetMapping("/me")
    public AuthDtos.UserResponse me(@AuthenticationPrincipal AppUserPrincipal principal) {
        return auth.currentUser(principal);
    }

    @PostMapping("/password")
    public AuthDtos.UserResponse changePassword(@Valid @RequestBody PasswordChangeRequest request,
            HttpServletRequest httpRequest, HttpServletResponse httpResponse) {
        return auth.changePassword(request, httpRequest, httpResponse);
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(HttpServletRequest request) {
        auth.logout(request);
        return ResponseEntity.status(HttpStatus.NO_CONTENT).build();
    }
}
