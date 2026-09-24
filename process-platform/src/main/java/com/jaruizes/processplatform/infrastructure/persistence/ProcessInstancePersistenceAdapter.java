package com.jaruizes.processplatform.infrastructure.persistence;

import com.jaruizes.processplatform.domain.model.*;
import com.jaruizes.processplatform.domain.ports.ProcessInstanceRepositoryPort;
import com.jaruizes.processplatform.infrastructure.persistence.entity.*;
import com.jaruizes.processplatform.infrastructure.persistence.repository.*;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.*;

@Component
public class ProcessInstancePersistenceAdapter
        implements ProcessInstanceRepositoryPort {

    private final SpringProcessInstanceRepository repository;
    private final SpringProcessDefinitionRepository definitionRepository;

    public ProcessInstancePersistenceAdapter(
            SpringProcessInstanceRepository repository,
            SpringProcessDefinitionRepository definitionRepository) {
        this.repository = repository;
        this.definitionRepository = definitionRepository;
    }

    @Override
    @Transactional
    public ProcessInstance create(ProcessInstance instance) {
        if (repository.existsById(instance.id())) {
            throw new IllegalArgumentException(
                    "Process instance already exists: " + instance.id());
        }
        var definition = definitionRepository.findById(instance.definitionId())
                .orElseThrow(() -> new NoSuchElementException(
                        "Process definition not found: " + instance.definitionId()));

        var entity = new ProcessInstanceJpaEntity();
        entity.setId(instance.id());
        entity.setDefinition(definition);
        entity.setDefinitionKey(instance.definitionKey());
        entity.setDefinitionVersion(instance.definitionVersion());
        entity.setStatus(instance.status());
        entity.setCorrelationId(instance.correlationId());
        entity.setInput(new LinkedHashMap<>(instance.input()));
        entity.setContext(new LinkedHashMap<>(instance.context()));
        entity.setCreatedAt(instance.createdAt());
        entity.setUpdatedAt(instance.updatedAt());
        entity.setCompletedAt(instance.completedAt());
        entity.replaceSteps(instance.steps().stream().map(step -> {
            var result = new ProcessStepInstanceJpaEntity();
            result.setId(step.id());
            result.setStepDefinitionId(step.stepDefinitionId());
            result.setStepKey(step.stepKey());
            result.setType(step.type());
            result.setStatus(step.status());
            result.setInput(new LinkedHashMap<>(safe(step.input())));
            result.setOutput(new LinkedHashMap<>(safe(step.output())));
            result.setError(new LinkedHashMap<>(safe(step.error())));
            result.setDelegatedExecutionId(step.delegatedExecutionId());
            result.setAttemptCount(step.attemptCount());
            result.setAvailableAt(step.availableAt());
            result.setDeadlineAt(step.deadlineAt());
            result.setStartedAt(step.startedAt());
            result.setCompletedAt(step.completedAt());
            result.setUpdatedAt(step.updatedAt());
            return result;
        }).toList());

        return toDomain(repository.saveAndFlush(entity));
    }

    @Override
    @Transactional(readOnly = true)
    public Optional<ProcessInstance> findById(UUID id) {
        return repository.findById(id).map(this::toDomain);
    }

    @Override
    @Transactional(readOnly = true)
    public List<ProcessInstance> findAll() {
        return repository.findAll().stream()
                .map(this::toDomain)
                .sorted(Comparator.comparing(ProcessInstance::createdAt).reversed())
                .toList();
    }

    @Override
    @Transactional
    public ProcessInstance updateContext(UUID id, Map<String,Object> context) {
        var entity = repository.findById(id)
                .orElseThrow(() -> new NoSuchElementException(
                        "Process instance not found: " + id));
        entity.setContext(new LinkedHashMap<>(context));
        entity.setUpdatedAt(Instant.now());
        return toDomain(repository.saveAndFlush(entity));
    }

    private ProcessInstance toDomain(ProcessInstanceJpaEntity entity) {
        return new ProcessInstance(
                entity.getId(),
                entity.getDefinition().getId(),
                entity.getDefinitionKey(),
                entity.getDefinitionVersion(),
                entity.getStatus(),
                entity.getCorrelationId(),
                entity.getInput(),
                entity.getContext(),
                entity.getSteps().stream().map(step ->
                        new ProcessStepInstance(
                                step.getId(),
                                entity.getId(),
                                step.getStepDefinitionId(),
                                step.getStepKey(),
                                step.getType(),
                                step.getStatus(),
                                step.getInput(),
                                step.getOutput(),
                                step.getError(),
                                step.getDelegatedExecutionId(),
                                step.getAttemptCount(),
                                step.getAvailableAt(),
                                step.getDeadlineAt(),
                                step.getStartedAt(),
                                step.getCompletedAt(),
                                step.getUpdatedAt()
                        )
                ).toList(),
                entity.getCreatedAt(),
                entity.getUpdatedAt(),
                entity.getCompletedAt()
        );
    }

    private static Map<String,Object> safe(Map<String,Object> value) {
        return value == null ? Map.of() : value;
    }
}
