package com.jaruizes.processplatform.domain.model;

public record PreparedAgentExecution(
        AgentExecutionSubmission submission,
        ExecutionCommand command) {}
