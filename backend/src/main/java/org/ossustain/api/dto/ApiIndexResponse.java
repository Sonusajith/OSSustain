package org.ossustain.api.dto;

import java.util.Map;

public record ApiIndexResponse(
        String service,
        String version,
        String dashboard,
        Map<String, String> endpoints) {
}
