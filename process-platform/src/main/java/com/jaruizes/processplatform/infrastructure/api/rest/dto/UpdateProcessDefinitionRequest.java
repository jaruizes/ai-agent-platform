package com.jaruizes.processplatform.infrastructure.api.rest.dto;

import jakarta.validation.Valid;

import java.util.List;
import java.util.Map;

public record UpdateProcessDefinitionRequest(
        String name,
        String description,
        Map<String,Object> inputSchema,
        Map<String,Object> outputSchema,
        List<@Valid ProcessStepDefinitionRequest> steps) {}
