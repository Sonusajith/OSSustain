package org.ossustain.security;

import org.ossustain.api.analysis.AnalysisResponse;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1/admin")
public class AdminController {
    private final AdminService admin;

    public AdminController(AdminService admin) { this.admin = admin; }

    @GetMapping("/users")
    public AuthDtos.AdminUserPage users(@RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int pageSize) {
        return admin.listUsers(page, pageSize);
    }

    @PostMapping("/users")
    public ResponseEntity<AuthDtos.CreatedUserResponse> createUser(@AuthenticationPrincipal AppUserPrincipal actor,
            @Valid @RequestBody CreateUserRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(admin.createUser(actor.id(), request));
    }

    @PatchMapping("/users/{id}/enabled")
    public AuthDtos.AdminUserResponse setUserEnabled(@AuthenticationPrincipal AppUserPrincipal actor,
            @PathVariable long id, @Valid @RequestBody SetEnabledRequest request) {
        return admin.setEnabled(actor.id(), id, request.enabled());
    }

    @GetMapping("/analyses")
    public AuthDtos.AdminAnalysisPage analyses(@RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int pageSize) {
        return admin.listAnalyses(page, pageSize);
    }

    @PostMapping("/analyses/{id}/cancel")
    public AnalysisResponse cancel(@AuthenticationPrincipal AppUserPrincipal actor, @PathVariable UUID id) {
        return admin.cancelAnalysis(actor.id(), id);
    }
}
