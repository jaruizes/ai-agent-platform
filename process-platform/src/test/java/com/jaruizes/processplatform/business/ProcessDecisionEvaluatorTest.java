package com.jaruizes.processplatform.business;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.*;

class ProcessDecisionEvaluatorTest {

    private final ProcessDecisionEvaluator evaluator = new ProcessDecisionEvaluator();

    @Test
    void evaluatesNestedPathAndOutcome() {
        var result = evaluator.evaluate(
                Map.of("processInput", Map.of("score", 85)),
                Map.of(
                        "path", "processInput.score",
                        "operator", "GTE",
                        "value", 80,
                        "onTrue", "HIGH",
                        "onFalse", "LOW"));

        assertThat(result)
                .containsEntry("outcome", "HIGH")
                .containsEntry("matched", true)
                .containsEntry("actual", 85);
    }

    @Test
    void matchesConditionalBranchAgainstDecisionContext() {
        assertThat(evaluator.conditionMatches(
                Map.of("route", Map.of("outcome", "HUMAN")),
                Map.of("decisionStep", "route", "equals", "HUMAN")))
                .isTrue();

        assertThat(evaluator.conditionMatches(
                Map.of("route", Map.of("outcome", "AUTO")),
                Map.of("decisionStep", "route", "equals", "HUMAN")))
                .isFalse();
    }
}
