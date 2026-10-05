package com.jaruizes.processplatform.infrastructure.api.rest.dto;

import jakarta.validation.constraints.NotBlank;
import java.util.Map;

public record CompleteHumanTaskRequest(
        @NotBlank String decision,
        Map<String,Object> result) {}
