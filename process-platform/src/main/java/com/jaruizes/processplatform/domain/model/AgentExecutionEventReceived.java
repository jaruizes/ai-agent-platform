package com.jaruizes.processplatform.domain.model;

/**
 * Internal Process Platform event. Future process orchestration code can react
 * to it without depending on NATS or JSON.
 */
public record AgentExecutionEventReceived(ExecutionEvent event) {}
