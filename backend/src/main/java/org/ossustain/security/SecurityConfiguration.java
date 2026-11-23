package org.ossustain.security;

import tools.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletResponse;
import org.ossustain.api.dto.ApiErrorResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.ProviderManager;
import org.springframework.security.authentication.dao.DaoAuthenticationProvider;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.Authentication;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.security.web.csrf.HttpSessionCsrfTokenRepository;
import org.springframework.security.web.csrf.CsrfTokenRepository;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.io.IOException;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Arrays;

@Configuration
@EnableMethodSecurity
public class SecurityConfiguration {
    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder(12);
    }

    @Bean
    AuthenticationManager authenticationManager(AppUserDetailsService users, PasswordEncoder passwords) {
        DaoAuthenticationProvider provider = new DaoAuthenticationProvider(users);
        provider.setPasswordEncoder(passwords);
        return new ProviderManager(provider);
    }

    @Bean
    SecurityContextRepository securityContextRepository() {
        return new HttpSessionSecurityContextRepository();
    }

    @Bean
    CsrfTokenRepository csrfTokenRepository() {
        return new HttpSessionCsrfTokenRepository();
    }

    @Bean
    CorsConfigurationSource corsConfigurationSource(
            @Value("${ossustain.cors.allowed-origins:http://localhost:5173}") String origins) {
        CorsConfiguration cors = new CorsConfiguration();
        cors.setAllowedOrigins(Arrays.stream(origins.split(",")).map(String::trim).toList());
        cors.setAllowCredentials(true);
        cors.setAllowedMethods(Arrays.asList("GET", "POST", "PATCH", "OPTIONS"));
        cors.setAllowedHeaders(Arrays.asList("Accept", "Content-Type", "X-CSRF-TOKEN"));
        cors.setMaxAge(3600L);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", cors);
        return source;
    }

    @Bean
    SecurityFilterChain securityFilterChain(HttpSecurity http, ObjectMapper objectMapper,
            SecurityContextRepository contextRepository, CsrfTokenRepository csrfRepository) throws Exception {
        http
                .cors(Customizer.withDefaults())
                .csrf(csrf -> csrf.csrfTokenRepository(csrfRepository))
                .securityContext(context -> context.securityContextRepository(contextRepository))
                .sessionManagement(session -> session
                        .sessionCreationPolicy(SessionCreationPolicy.IF_REQUIRED)
                        .sessionFixation(fixation -> fixation.changeSessionId()))
                .authorizeHttpRequests(authorize -> authorize
                        .requestMatchers("/api/v1/auth/csrf", "/api/v1/auth/login").permitAll()
                        .requestMatchers("/api/v1/auth/me", "/api/v1/auth/password", "/api/v1/auth/logout")
                            .hasAnyAuthority("ROLE_ADMIN", "ROLE_RESEARCHER", "ROLE_PASSWORD_CHANGE_REQUIRED")
                        .requestMatchers("/api/v1/auth/**").authenticated()
                        .requestMatchers("/api/v1/admin/**").hasRole("ADMIN")
                        .requestMatchers(HttpMethod.GET, "/api/v1/analyses/**").hasAnyRole("ADMIN", "RESEARCHER")
                        .requestMatchers(HttpMethod.POST, "/api/v1/analyses").hasAnyRole("ADMIN", "RESEARCHER")
                        .requestMatchers(HttpMethod.GET, "/api/v1", "/api/v1/", "/api/v1/repositories/**",
                                "/api/v1/research/**", "/api/v1/compare", "/openapi.yaml", "/actuator/health")
                            .permitAll()
                        .requestMatchers("/api/v1/**").denyAll()
                        .anyRequest().permitAll())
                .exceptionHandling(errors -> errors
                        .authenticationEntryPoint((request, response, exception) -> writeError(
                                objectMapper, response, HttpStatus.UNAUTHORIZED, "authentication_required",
                                "Sign in to access this resource.", request.getRequestURI()))
                        .accessDeniedHandler((request, response, exception) -> writeError(
                                objectMapper, response, HttpStatus.FORBIDDEN, "access_denied",
                                "You do not have permission to access this resource.", request.getRequestURI())));
        return http.build();
    }

    @Bean
    org.springframework.boot.CommandLineRunner bootstrapAdministrator(
            JdbcTemplate jdbc, PasswordEncoder passwords,
            @Value("${ossustain.security.bootstrap-admin-username:}") String username,
            @Value("${ossustain.security.bootstrap-admin-password:}") String password) {
        return args -> {
            if (username.isBlank() && password.isBlank()) return;
            if (username.isBlank() || password.isBlank() || password.length() < 16) {
                throw new IllegalStateException(
                        "Set both OSSUSTAIN_ADMIN_USERNAME and a 16-character OSSUSTAIN_ADMIN_PASSWORD.");
            }
            String normalized = username.trim().toLowerCase(java.util.Locale.ROOT);
            if (!normalized.matches("^[a-z0-9][a-z0-9._-]{2,99}$")) {
                throw new IllegalStateException("OSSUSTAIN_ADMIN_USERNAME must be 3–100 valid username characters.");
            }
            Integer exists = jdbc.queryForObject("SELECT count(*) FROM app_users WHERE username = ?",
                    Integer.class, normalized);
            if (exists != null && exists > 0) return;
            Long userId = jdbc.queryForObject("""
                    INSERT INTO app_users (username, password_hash, must_change_password)
                    VALUES (?, ?, TRUE) RETURNING id
                    """, Long.class, normalized, passwords.encode(password));
            jdbc.update("INSERT INTO app_user_roles (user_id, role) VALUES (?, 'ADMIN')", userId);
        };
    }

    private static void writeError(ObjectMapper mapper, HttpServletResponse response, HttpStatus status,
            String code, String message, String path) throws IOException {
        response.setStatus(status.value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        mapper.writeValue(response.getOutputStream(), new ApiErrorResponse(
                OffsetDateTime.now(ZoneOffset.UTC), status.value(), code, message, path));
    }
}
