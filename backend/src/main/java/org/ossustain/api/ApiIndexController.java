package org.ossustain.api;

import org.ossustain.api.dto.ApiIndexResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.beans.factory.annotation.Value;

import java.util.Map;

@RestController
public class ApiIndexController {
    private final String frontendUrl;

    public ApiIndexController(@Value("${ossustain.frontend.url:http://localhost:5173}") String frontendUrl) {
        this.frontendUrl = frontendUrl;
    }

    @GetMapping({"/api/v1", "/api/v1/"})
    public ApiIndexResponse index() {
        return new ApiIndexResponse(
                "OSSustain Read API",
                "v1",
                "Open the OSSustain dashboard at " + frontendUrl + ".",
                Map.of(
                        "repositories", "/api/v1/repositories",
                        "compare", "/api/v1/compare",
                        "research", "/api/v1/research",
                        "openapi", "/openapi.yaml",
                        "health", "/actuator/health"));
    }
}
