package com.jaruizes.processplatform.domain.model;

import java.util.UUID;

public record PendingExecutionCommand(
        UUID outboxId,
        ExecutionCommand command) {}
