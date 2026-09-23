package com.jaruizes.processplatform.domain.ports;

import com.jaruizes.processplatform.domain.model.PendingExecutionCommand;

import java.util.List;
import java.util.UUID;

public interface ExecutionCommandOutboxPort {
    List<PendingExecutionCommand> pending(int limit);
    void markPublished(UUID outboxId);
    void markAttempt(UUID outboxId);
}
