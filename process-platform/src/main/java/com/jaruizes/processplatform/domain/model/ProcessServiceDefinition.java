package com.jaruizes.processplatform.domain.model;

import java.time.Instant;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

public record ProcessServiceDefinition(
        UUID id,
        String serviceKey,
        String name,
        String description,
        int version,
        ProcessServiceStatus status,
        String implementationKey,
        Map<String,Object> inputSchema,
        Map<String,Object> outputSchema,
        Instant createdAt,
        Instant updatedAt,
        Instant activatedAt) {

    public ProcessServiceDefinition {
        inputSchema = inputSchema == null ? Map.of()
                : Collections.unmodifiableMap(new LinkedHashMap<>(inputSchema));
        outputSchema = outputSchema == null ? Map.of()
                : Collections.unmodifiableMap(new LinkedHashMap<>(outputSchema));
    }
}
