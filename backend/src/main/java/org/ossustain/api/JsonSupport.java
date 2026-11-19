package org.ossustain.api;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.node.JsonNodeFactory;
import org.springframework.stereotype.Component;

@Component
public final class JsonSupport {
    private final ObjectMapper objectMapper;

    public JsonSupport(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public JsonNode read(String value) {
        if (value == null || value.isBlank()) {
            return JsonNodeFactory.instance.objectNode();
        }
        try {
            return objectMapper.readTree(value);
        } catch (Exception error) {
            throw new IllegalStateException("Stored JSON could not be decoded", error);
        }
    }
}
