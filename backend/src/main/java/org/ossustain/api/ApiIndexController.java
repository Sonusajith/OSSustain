package org.ossustain.api;

import org.ossustain.api.dto.ApiIndexResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class ApiIndexController {
    @GetMapping({"/api/v1", "/api/v1/"})
    public ApiIndexResponse index() {
        return new ApiIndexResponse(
                "OSSustain Read API",
                "v1",
                "For the dashboard, start the frontend with pnpm dev and open http://localhost:5173.",
                Map.of(
                        "repositories", "/api/v1/repositories",
                        "research", "/api/v1/research",
                        "openapi", "/openapi.yaml",
                        "health", "/actuator/health"));
    }
}
