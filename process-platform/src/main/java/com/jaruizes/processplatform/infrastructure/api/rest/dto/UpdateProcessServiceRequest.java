package com.jaruizes.processplatform.infrastructure.api.rest.dto;

import jakarta.validation.constraints.NotBlank;
import java.util.Map;

public record UpdateProcessServiceRequest(
        @NotBlank String name,
        String description,
        @NotBlank String implementationKey,
        Map<String,Object> configuration,
        Map<String,Object> inputSchema,
        Map<String,Object> outputSchema) {}
