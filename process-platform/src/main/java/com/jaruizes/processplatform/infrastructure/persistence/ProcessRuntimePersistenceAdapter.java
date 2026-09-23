package com.jaruizes.processplatform.infrastructure.persistence;

import com.jaruizes.processplatform.domain.model.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.jaruizes.processplatform.domain.ports.ProcessRuntimeRepositoryPort;
import com.jaruizes.processplatform.infrastructure.persistence.entity.*;
import com.jaruizes.processplatform.infrastructure.persistence.repository.*;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.*;

@Component
public class ProcessRuntimePersistenceAdapter
        implements ProcessRuntimeRepositoryPort {

    private final SpringProcessInstanceRepository instances;
    private final SpringProcessStepInstanceRepository steps;
    private final SpringProcessExecutionCommandOutboxRepository outbox;
    private final ObjectMapper objectMapper;

    public ProcessRuntimePersistenceAdapter(
            SpringProcessInstanceRepository instances,
            SpringProcessStepInstanceRepository steps,
            SpringProcessExecutionCommandOutboxRepository outbox,
            ObjectMapper objectMapper) {
        this.instances = instances;
        this.steps = steps;
        this.outbox = outbox;
        this.objectMapper = objectMapper;
    }

    @Override
    @Transactional(readOnly = true)
    public Optional<ProcessInstance> findInstance(UUID instanceId) {
        return instances.findById(instanceId).map(this::toDomain);
    }

    @Override
    @Transactional(readOnly = true)
    public Optional<ProcessInstance> findByDelegatedExecutionId(UUID executionId) {
        return steps.findByDelegatedExecutionId(executionId)
                .map(ProcessStepInstanceJpaEntity::getInstance)
                .map(this::toDomain);
    }

    @Override
    @Transactional(readOnly = true)
    public List<ProcessInstance> findRunnableInstances() {
        return instances.findAll().stream()
                .filter(entity -> entity.getStatus() == ProcessInstanceStatus.RUNNING
                        || entity.getStatus() == ProcessInstanceStatus.WAITING)
                .map(this::toDomain)
                .toList();
    }

    @Override
    @Transactional
    public ProcessInstance updateInstanceStatus(
            UUID instanceId,
            ProcessInstanceStatus status) {
        var entity = requireInstance(instanceId);
        entity.setStatus(status);
        entity.setUpdatedAt(Instant.now());
        return toDomain(instances.saveAndFlush(entity));
    }

    @Override
    @Transactional
    public boolean markReady(UUID instanceId, String stepKey) {
        var step = requireStep(instanceId, stepKey);
        if (step.getStatus() != ProcessStepStatus.PENDING) return false;
        step.setStatus(ProcessStepStatus.READY);
        step.setUpdatedAt(Instant.now());
        steps.saveAndFlush(step);
        return true;
    }

    @Override
    @Transactional
    public boolean claimReady(
            UUID instanceId,
            String stepKey,
            Map<String,Object> input) {
        var step = requireStep(instanceId, stepKey);
        if (step.getStatus() != ProcessStepStatus.READY) return false;
        step.setStatus(ProcessStepStatus.RUNNING);
        step.setInput(new LinkedHashMap<>(input));
        step.setStartedAt(step.getStartedAt() == null ? Instant.now() : step.getStartedAt());
        step.setUpdatedAt(Instant.now());
        steps.saveAndFlush(step);
        return true;
    }

    @Override
    @Transactional
    public ProcessInstance delegateAgent(
            UUID instanceId,
            String stepKey,
            ExecutionCommand command) {
        var step = requireStep(instanceId, stepKey);
        step.setStatus(ProcessStepStatus.WAITING);
        step.setDelegatedExecutionId(command.data().execution().executionId());
        step.setUpdatedAt(Instant.now());
        steps.save(step);

        var outboxEntity = new ProcessExecutionCommandOutboxJpaEntity();
        outboxEntity.setId(UUID.randomUUID());
        outboxEntity.setProcessInstanceId(instanceId);
        outboxEntity.setStepKey(stepKey);
        outboxEntity.setExecutionId(command.data().execution().executionId());
        outboxEntity.setMessageId(command.messageId());
        outboxEntity.setPayload(objectMapper.convertValue(command, Map.class));
        outboxEntity.setAttempts(0);
        outboxEntity.setCreatedAt(Instant.now());
        outbox.save(outboxEntity);

        var instance = requireInstance(instanceId);
        instance.setUpdatedAt(Instant.now());
        return toDomain(instances.saveAndFlush(instance));
    }

    @Override
    @Transactional
    public ProcessInstance completeStep(
            UUID instanceId,
            String stepKey,
            Map<String,Object> output) {
        var step = requireStep(instanceId, stepKey);
        step.setStatus(ProcessStepStatus.COMPLETED);
        step.setOutput(new LinkedHashMap<>(output));
        step.setError(new LinkedHashMap<>());
        step.setCompletedAt(Instant.now());
        step.setUpdatedAt(Instant.now());
        steps.save(step);

        var instance = instances.findLockedById(instanceId)
                .orElseThrow(() -> new NoSuchElementException(
                        "Process instance not found: " + instanceId));
        var mergedContext = new LinkedHashMap<>(instance.getContext());
        mergedContext.put(stepKey, new LinkedHashMap<>(output));
        instance.setContext(mergedContext);
        instance.setStatus(ProcessInstanceStatus.RUNNING);
        instance.setUpdatedAt(Instant.now());
        return toDomain(instances.saveAndFlush(instance));
    }

    @Override
    @Transactional
    public ProcessInstance failStep(
            UUID instanceId,
            String stepKey,
            Map<String,Object> error) {
        var step = requireStep(instanceId, stepKey);
        step.setStatus(ProcessStepStatus.FAILED);
        step.setError(new LinkedHashMap<>(error));
        step.setCompletedAt(Instant.now());
        step.setUpdatedAt(Instant.now());
        steps.save(step);

        var instance = requireInstance(instanceId);
        instance.setStatus(ProcessInstanceStatus.FAILED);
        instance.setCompletedAt(Instant.now());
        instance.setUpdatedAt(Instant.now());
        return toDomain(instances.saveAndFlush(instance));
    }

    @Override
    @Transactional
    public ProcessInstance completeInstance(UUID instanceId) {
        var instance = requireInstance(instanceId);
        instance.setStatus(ProcessInstanceStatus.COMPLETED);
        instance.setCompletedAt(Instant.now());
        instance.setUpdatedAt(Instant.now());
        return toDomain(instances.saveAndFlush(instance));
    }

    @Override
    @Transactional
    public ProcessInstance failInstance(UUID instanceId) {
        var instance = requireInstance(instanceId);
        instance.setStatus(ProcessInstanceStatus.FAILED);
        instance.setCompletedAt(Instant.now());
        instance.setUpdatedAt(Instant.now());
        return toDomain(instances.saveAndFlush(instance));
    }

    private ProcessInstanceJpaEntity requireInstance(UUID id) {
        return instances.findById(id)
                .orElseThrow(() -> new NoSuchElementException(
                        "Process instance not found: " + id));
    }

    private ProcessStepInstanceJpaEntity requireStep(UUID instanceId, String stepKey) {
        return steps.findByInstanceIdAndStepKey(instanceId, stepKey)
                .orElseThrow(() -> new NoSuchElementException(
                        "Process step '%s' not found in instance %s"
                                .formatted(stepKey, instanceId)));
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
}
