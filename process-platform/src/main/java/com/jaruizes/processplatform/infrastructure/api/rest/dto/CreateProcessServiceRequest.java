package com.jaruizes.processplatform.infrastructure.api.rest.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

import java.util.Map;

public record CreateProcessServiceRequest(
        @NotBlank String serviceKey,
        @NotBlank String name,
        String description,
        @Min(1) int version,
        @NotBlank String implementationKey,
        Map<String,Object> configuration,
        Map<String,Object> inputSchema,
        Map<String,Object> outputSchema) {}
