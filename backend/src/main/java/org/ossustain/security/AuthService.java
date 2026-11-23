package org.ossustain.security;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.ossustain.api.ApiException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.security.web.csrf.CsrfTokenRepository;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class AuthService {
    private final AuthenticationManager authenticationManager;
    private final SecurityContextRepository securityContextRepository;
    private final CsrfTokenRepository csrfTokenRepository;
    private final PasswordEncoder passwordEncoder;
    private final AppUserDetailsService users;
    private final JdbcTemplate jdbc;

    public AuthService(AuthenticationManager authenticationManager,
            SecurityContextRepository securityContextRepository, CsrfTokenRepository csrfTokenRepository,
            PasswordEncoder passwordEncoder, AppUserDetailsService users, JdbcTemplate jdbc) {
        this.authenticationManager = authenticationManager;
        this.securityContextRepository = securityContextRepository;
        this.csrfTokenRepository = csrfTokenRepository;
        this.passwordEncoder = passwordEncoder;
        this.users = users;
        this.jdbc = jdbc;
    }

    public AuthDtos.UserResponse login(LoginRequest request, HttpServletRequest httpRequest,
            HttpServletResponse httpResponse) {
        if (request == null || request.username() == null || request.password() == null) {
            throw invalidCredentials();
        }
        Authentication authentication;
        try {
            authentication = authenticationManager.authenticate(
                    org.springframework.security.authentication.UsernamePasswordAuthenticationToken.unauthenticated(
                            request.username().trim().toLowerCase(java.util.Locale.ROOT), request.password()));
        } catch (org.springframework.security.core.AuthenticationException error) {
            throw invalidCredentials();
        }
        httpRequest.getSession(true);
        httpRequest.changeSessionId();
        csrfTokenRepository.saveToken(null, httpRequest, httpResponse);
        var context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(authentication);
        SecurityContextHolder.setContext(context);
        securityContextRepository.saveContext(context, httpRequest, httpResponse);
        return profile((AppUserPrincipal) authentication.getPrincipal());
    }

    public void logout(HttpServletRequest request) {
        var session = request.getSession(false);
        if (session != null) session.invalidate();
        SecurityContextHolder.clearContext();
    }

    @Transactional
    public AuthDtos.UserResponse changePassword(PasswordChangeRequest body,
            HttpServletRequest request, HttpServletResponse response) {
        Authentication current = SecurityContextHolder.getContext().getAuthentication();
        AppUserPrincipal principal = (AppUserPrincipal) current.getPrincipal();
        if (body == null || body.currentPassword() == null || body.newPassword() == null
                || body.newPassword().length() < 16 || body.newPassword().length() > 200
                || !passwordEncoder.matches(body.currentPassword(), principal.password())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "invalid_password_change",
                    "Enter the current password and a new password of at least 16 characters.");
        }
        jdbc.update("UPDATE app_users SET password_hash = ?, must_change_password = FALSE, updated_at = now() WHERE id = ?",
                passwordEncoder.encode(body.newPassword()), principal.id());
        AppUserPrincipal refreshed = users.loadUserByUsername(principal.username());
        var updated = org.springframework.security.authentication.UsernamePasswordAuthenticationToken.authenticated(
                refreshed, null, refreshed.getAuthorities());
        var context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(updated);
        SecurityContextHolder.setContext(context);
        securityContextRepository.saveContext(context, request, response);
        return profile(refreshed);
    }

    public AuthDtos.UserResponse currentUser(AppUserPrincipal principal) {
        return profile(users.loadUserByUsername(principal.username()));
    }

    private AuthDtos.UserResponse profile(AppUserPrincipal principal) {
        List<String> roles = principal.roles();
        return new AuthDtos.UserResponse(principal.id(), principal.username(), roles,
                principal.mustChangePassword());
    }

    private ApiException invalidCredentials() {
        return new ApiException(HttpStatus.UNAUTHORIZED, "invalid_credentials", "The username or password is incorrect.");
    }
}
