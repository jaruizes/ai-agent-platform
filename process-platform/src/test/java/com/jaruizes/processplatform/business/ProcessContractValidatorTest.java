package com.jaruizes.processplatform.business;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.*;

class ProcessContractValidatorTest {

    private final ProcessContractValidator validator = new ProcessContractValidator();

    @Test
    void validatesRequiredNestedProperties() {
        var schema = Map.<String,Object>of(
                "type", "object",
                "required", List.of("processInput"),
                "properties", Map.of(
                        "processInput", Map.of(
                                "type", "object",
                                "required", List.of("id"),
                                "properties", Map.of(
                                        "id", Map.of("type", "string")
                                )
                        )
                )
        );

        validator.validate(
                "step.input",
                schema,
                Map.of("processInput", Map.of("id", "P-1")));

        assertThatThrownBy(() -> validator.validate(
                "step.input",
                schema,
                Map.of("processInput", Map.of())))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("required property 'id'");
    }

    @Test
    void rejectsWrongPrimitiveTypes() {
        assertThatThrownBy(() -> validator.validate(
                "step.output",
                Map.of("type", "object",
                        "properties", Map.of(
                                "score", Map.of("type", "number"))),
                Map.of("score", "high")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("schema type 'number'");
    }
}
