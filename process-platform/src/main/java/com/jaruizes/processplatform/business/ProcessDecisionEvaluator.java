package com.jaruizes.processplatform.business;

import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.*;

@Component
public class ProcessDecisionEvaluator {

    public Map<String,Object> evaluate(
            Map<String,Object> input,
            Map<String,Object> configuration) {

        var path = required(configuration, "path");
        var operator = required(configuration, "operator").toUpperCase(Locale.ROOT);
        var actual = readPath(input, path);
        var expected = configuration.get("value");

        var matched = switch (operator) {
            case "EQ" -> Objects.equals(normalize(actual), normalize(expected));
            case "NE" -> !Objects.equals(normalize(actual), normalize(expected));
            case "GT" -> compare(actual, expected) > 0;
            case "GTE" -> compare(actual, expected) >= 0;
            case "LT" -> compare(actual, expected) < 0;
            case "LTE" -> compare(actual, expected) <= 0;
            case "EXISTS" -> actual != null;
            case "IN" -> expected instanceof Collection<?> values
                    && values.stream().map(this::normalize).anyMatch(v -> Objects.equals(v, normalize(actual)));
            default -> throw new IllegalArgumentException("Unsupported DECISION operator: " + operator);
        };

        var output = new LinkedHashMap<String,Object>();
        output.put("outcome", matched
                ? String.valueOf(configuration.getOrDefault("onTrue", "TRUE"))
                : String.valueOf(configuration.getOrDefault("onFalse", "FALSE")));
        output.put("matched", matched);
        if (actual != null) output.put("actual", actual);
        return output;
    }

    public boolean conditionMatches(
            Map<String,Object> processContext,
            Map<String,Object> condition) {
        var decisionStep = required(condition, "decisionStep");
        var expected = String.valueOf(condition.get("equals"));
        var decision = processContext.get(decisionStep);
        if (!(decision instanceof Map<?,?> values)) return false;
        return Objects.equals(expected, String.valueOf(values.get("outcome")));
    }

    private Object readPath(Map<String,Object> root, String path) {
        Object current = root;
        for (var segment : path.split("\\.")) {
            if (!(current instanceof Map<?,?> map)) return null;
            current = map.get(segment);
        }
        return current;
    }

    private int compare(Object left,Object right) {
        if(left==null||right==null) throw new IllegalArgumentException("DECISION comparison requires non-null values");
        if(left instanceof Number || right instanceof Number) {
            return new BigDecimal(String.valueOf(left)).compareTo(new BigDecimal(String.valueOf(right)));
        }
        return String.valueOf(left).compareTo(String.valueOf(right));
    }

    private Object normalize(Object value) {
        if(value instanceof Number) return new BigDecimal(String.valueOf(value));
        return value;
    }

    private static String required(Map<String,Object> config,String key) {
        var value=config.get(key);
        if(value==null||String.valueOf(value).isBlank())
            throw new IllegalArgumentException("DECISION requires configuration."+key);
        return String.valueOf(value);
    }
}
