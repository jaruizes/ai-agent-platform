package com.jaruizes.processplatform.infrastructure.persistence;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.jaruizes.processplatform.domain.model.ExecutionCommand;
import com.jaruizes.processplatform.domain.model.PendingExecutionCommand;
import com.jaruizes.processplatform.domain.ports.ExecutionCommandOutboxPort;
import com.jaruizes.processplatform.infrastructure.persistence.repository.SpringProcessExecutionCommandOutboxRepository;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Component
public class ExecutionCommandOutboxPersistenceAdapter
        implements ExecutionCommandOutboxPort {

    private final SpringProcessExecutionCommandOutboxRepository repository;
    private final ObjectMapper objectMapper;

    public ExecutionCommandOutboxPersistenceAdapter(
            SpringProcessExecutionCommandOutboxRepository repository,
            ObjectMapper objectMapper) {
        this.repository = repository;
        this.objectMapper = objectMapper;
    }

    @Override
    @Transactional(readOnly = true)
    public List<PendingExecutionCommand> pending(int limit) {
        return repository.findByPublishedAtIsNullOrderByCreatedAtAsc(
                        PageRequest.of(0, Math.max(1, limit)))
                .stream()
                .map(entity -> new PendingExecutionCommand(
                        entity.getId(),
                        objectMapper.convertValue(
                                entity.getPayload(),
                                ExecutionCommand.class)))
                .toList();
    }

    @Override
    @Transactional
    public void markPublished(UUID outboxId) {
        repository.findById(outboxId).ifPresent(entity -> {
            entity.setPublishedAt(Instant.now());
            entity.setAttempts(entity.getAttempts() + 1);
            repository.save(entity);
        });
    }

    @Override
    @Transactional
    public void markAttempt(UUID outboxId) {
        repository.findById(outboxId).ifPresent(entity -> {
            entity.setAttempts(entity.getAttempts() + 1);
            repository.save(entity);
        });
    }
}
