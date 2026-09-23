package com.jaruizes.processplatform.business;

import org.springframework.stereotype.Component;

import java.util.*;

@Component
public class ProcessContractValidator {

    public void validate(String label, Map<String,Object> schema, Object value) {
        if (schema == null || schema.isEmpty()) return;
        validateValue(label, schema, value);
    }

    @SuppressWarnings("unchecked")
    private void validateValue(String path, Map<String,Object> schema, Object value) {
        var type = schema.get("type");
        if (type instanceof String expected && !matches(expected, value)) {
            throw new IllegalArgumentException(
                    "%s does not match schema type '%s'".formatted(path, expected));
        }

        if ("object".equals(type) && value instanceof Map<?,?> map) {
            var required = schema.get("required");
            if (required instanceof Collection<?> fields) {
                for (var field : fields) {
                    if (!map.containsKey(String.valueOf(field))) {
                        throw new IllegalArgumentException(
                                "%s is missing required property '%s'"
                                        .formatted(path, field));
                    }
                }
            }

            var properties = schema.get("properties");
            if (properties instanceof Map<?,?> propertySchemas) {
                for (var entry : propertySchemas.entrySet()) {
                    var key = String.valueOf(entry.getKey());
                    if (!map.containsKey(key) || !(entry.getValue() instanceof Map<?,?> nested)) {
                        continue;
                    }
                    validateValue(
                            path + "." + key,
                            (Map<String,Object>) nested,
                            map.get(key));
                }
            }
        }

        if ("array".equals(type)
                && value instanceof Collection<?> values
                && schema.get("items") instanceof Map<?,?> itemSchema) {
            int index = 0;
            for (var item : values) {
                validateValue(
                        path + "[" + index++ + "]",
                        (Map<String,Object>) itemSchema,
                        item);
            }
        }
    }

    private static boolean matches(String type, Object value) {
        if (value == null) return true;
        return switch (type) {
            case "object" -> value instanceof Map<?,?>;
            case "array" -> value instanceof Collection<?>;
            case "string" -> value instanceof String;
            case "integer" -> value instanceof Byte || value instanceof Short
                    || value instanceof Integer || value instanceof Long;
            case "number" -> value instanceof Number;
            case "boolean" -> value instanceof Boolean;
            case "null" -> value == null;
            default -> true;
        };
    }
}
