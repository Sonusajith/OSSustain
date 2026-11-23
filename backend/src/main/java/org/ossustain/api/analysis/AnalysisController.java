package org.ossustain.api.analysis;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/analyses")
public class AnalysisController {
    private final AnalysisService service;

    public AnalysisController(AnalysisService service) { this.service = service; }

    @PostMapping
    public ResponseEntity<AnalysisResponse> submit(@RequestBody AnalysisRequest body, HttpServletRequest request) {
        String clientAddress = request.getHeader("X-Real-IP");
        if (clientAddress == null || clientAddress.isBlank()) clientAddress = request.getRemoteAddr();
        var response = service.submit(body == null ? null : body.repository(), clientAddress);
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .location(URI.create("/api/v1/analyses/" + response.id())).body(response);
    }

    @GetMapping("/{id}")
    public AnalysisResponse get(@PathVariable UUID id) { return service.get(id); }
}
