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
    public int claimReady(
            UUID instanceId,
            String stepKey,
            Map<String,Object> input,
            Long timeoutSeconds) {
        var step = requireStep(instanceId, stepKey);
        if (step.getStatus() != ProcessStepStatus.READY) return 0;
        var now = Instant.now();
        step.setStatus(ProcessStepStatus.RUNNING);
        step.setInput(new LinkedHashMap<>(input));
        step.setAttemptCount(step.getAttemptCount() + 1);
        step.setAvailableAt(null);
        step.setStartedAt(now);
        step.setDeadlineAt(timeoutSeconds == null || timeoutSeconds <= 0
                ? null : now.plusSeconds(timeoutSeconds));
        step.setUpdatedAt(now);
        steps.saveAndFlush(step);
        return step.getAttemptCount();
    }

    @Override
    @Transactional
    public boolean resetRunningStep(UUID instanceId, String stepKey, int expectedAttempt) {
        var step = requireStep(instanceId, stepKey);
        if (step.getStatus() != ProcessStepStatus.RUNNING
                || step.getAttemptCount() != expectedAttempt) return false;
        step.setStatus(ProcessStepStatus.READY);
        step.setStartedAt(null);
        step.setDeadlineAt(null);
        step.setUpdatedAt(Instant.now());
        steps.saveAndFlush(step);
        return true;
    }

    @Override
    @Transactional
    public boolean retryStep(
            UUID instanceId,
            String stepKey,
            int expectedAttempt,
            Map<String,Object> error,
            Instant availableAt) {
        var step = requireStep(instanceId, stepKey);
        if ((step.getStatus() != ProcessStepStatus.RUNNING
                && step.getStatus() != ProcessStepStatus.WAITING)
                || step.getAttemptCount() != expectedAttempt) {
            return false;
        }
        step.setStatus(ProcessStepStatus.READY);
        step.setError(new LinkedHashMap<>(error));
        step.setAvailableAt(availableAt);
        step.setDeadlineAt(null);
        step.setDelegatedExecutionId(null);
        step.setStartedAt(null);
        step.setUpdatedAt(Instant.now());
        steps.save(step);

        var instance = requireInstance(instanceId);
        if (instance.getStatus() != ProcessInstanceStatus.PAUSED) {
            instance.setStatus(ProcessInstanceStatus.RUNNING);
        }
        instance.setUpdatedAt(Instant.now());
        instances.saveAndFlush(instance);
        return true;
    }

    @Override
    @Transactional
    public boolean waitStep(UUID instanceId, String stepKey, int expectedAttempt) {
        var step = requireStep(instanceId, stepKey);
        if (step.getStatus() != ProcessStepStatus.RUNNING
                || step.getAttemptCount() != expectedAttempt) return false;
        step.setStatus(ProcessStepStatus.WAITING);
        step.setUpdatedAt(Instant.now());
        steps.save(step);

        var instance = requireInstance(instanceId);
        if (instance.getStatus() != ProcessInstanceStatus.PAUSED) {
            instance.setStatus(ProcessInstanceStatus.WAITING);
        }
        instance.setUpdatedAt(Instant.now());
        instances.saveAndFlush(instance);
        return true;
    }

    @Override
    @Transactional
    public ProcessInstance skipStep(
            UUID instanceId,
            String stepKey,
            Map<String,Object> output) {
        var step = requireStep(instanceId, stepKey);
        if (step.getStatus() == ProcessStepStatus.SKIPPED
                || step.getStatus() == ProcessStepStatus.COMPLETED) {
            return toDomain(requireInstance(instanceId));
        }
        step.setStatus(ProcessStepStatus.SKIPPED);
        step.setOutput(new LinkedHashMap<>(output == null ? Map.of() : output));
        step.setCompletedAt(Instant.now());
        step.setUpdatedAt(Instant.now());
        steps.saveAndFlush(step);
        return toDomain(requireInstance(instanceId));
    }

    @Override
    @Transactional
    public boolean delegateAgent(
            UUID instanceId,
            String stepKey,
            int expectedAttempt,
            ExecutionCommand command) {
        var step = requireStep(instanceId, stepKey);
        if (step.getStatus() != ProcessStepStatus.RUNNING
                || step.getAttemptCount() != expectedAttempt) return false;
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
        instances.saveAndFlush(instance);
        return true;
    }

    @Override
    @Transactional
    public boolean completeStep(
            UUID instanceId,
            String stepKey,
            int expectedAttempt,
            Map<String,Object> output) {
        var step = requireStep(instanceId, stepKey);
        if ((step.getStatus() != ProcessStepStatus.RUNNING
                && step.getStatus() != ProcessStepStatus.WAITING)
                || step.getAttemptCount() != expectedAttempt) {
            return false;
        }
        step.setStatus(ProcessStepStatus.COMPLETED);
        step.setOutput(new LinkedHashMap<>(output));
        step.setError(new LinkedHashMap<>());
        step.setAvailableAt(null);
        step.setDeadlineAt(null);
        step.setCompletedAt(Instant.now());
        step.setUpdatedAt(Instant.now());
        steps.save(step);

        var instance = instances.findLockedById(instanceId)
                .orElseThrow(() -> new NoSuchElementException(
                        "Process instance not found: " + instanceId));
        var mergedContext = new LinkedHashMap<>(instance.getContext());
        mergedContext.put(stepKey, new LinkedHashMap<>(output));
        instance.setContext(mergedContext);
        if (instance.getStatus() != ProcessInstanceStatus.PAUSED
                && instance.getStatus() != ProcessInstanceStatus.CANCELLED) {
            instance.setStatus(ProcessInstanceStatus.RUNNING);
        }
        instance.setUpdatedAt(Instant.now());
        instances.saveAndFlush(instance);
        return true;
    }

    @Override
    @Transactional
    public boolean failAttempt(
            UUID instanceId,
            String stepKey,
            int expectedAttempt,
            Map<String,Object> error) {
        var step = requireStep(instanceId, stepKey);
        if ((step.getStatus() != ProcessStepStatus.RUNNING
                && step.getStatus() != ProcessStepStatus.WAITING)
                || step.getAttemptCount() != expectedAttempt) {
            return false;
        }
        terminalFail(instanceId, step, error);
        return true;
    }

    @Override
    @Transactional
    @SuppressWarnings("unchecked")
    public ProcessInstance repeatReviewedStep(
            UUID instanceId,
            String producerStepKey,
            String reviewStepKey,
            int reviewAttempt,
            Map<String,Object> feedback) {

        var instance = instances.findLockedById(instanceId)
                .orElseThrow(() -> new NoSuchElementException(
                        "Process instance not found: " + instanceId));
        var producer = requireStep(instanceId, producerStepKey);
        var review = requireStep(instanceId, reviewStepKey);

        if (review.getStatus() != ProcessStepStatus.WAITING
                || review.getAttemptCount() != reviewAttempt) {
            throw new IllegalStateException(
                    "Review step '%s' is no longer waiting on attempt %d"
                            .formatted(reviewStepKey, reviewAttempt));
        }
        if (producer.getStatus() != ProcessStepStatus.COMPLETED) {
            throw new IllegalStateException(
                    "Reviewed producer step '%s' must be COMPLETED before it can repeat"
                            .formatted(producerStepKey));
        }

        var history = new LinkedHashMap<String,Object>();
        var existingHistory = instance.getContext().get("_reviewHistory");
        if (existingHistory instanceof Map<?,?> values) {
            values.forEach((key,value) -> history.put(String.valueOf(key), value));
        }

        var reviewEntries = new ArrayList<Map<String,Object>>();
        var existingEntries = history.get(reviewStepKey);
        if (existingEntries instanceof Collection<?> values) {
            for (var value : values) {
                if (value instanceof Map<?,?> map) {
                    var copy = new LinkedHashMap<String,Object>();
                    map.forEach((key,item) -> copy.put(String.valueOf(key), item));
                    reviewEntries.add(copy);
                }
            }
        }

        var entry = new LinkedHashMap<String,Object>();
        entry.put("iteration", reviewAttempt);
        entry.put("feedback", new LinkedHashMap<>(feedback == null ? Map.of() : feedback));
        entry.put("previousOutput", new LinkedHashMap<>(producer.getOutput()));
        entry.put("createdAt", Instant.now().toString());
        reviewEntries.add(entry);
        history.put(reviewStepKey, reviewEntries);

        var mergedContext = new LinkedHashMap<>(instance.getContext());
        mergedContext.put("_reviewHistory", history);
        instance.setContext(mergedContext);
        if (instance.getStatus() != ProcessInstanceStatus.PAUSED) {
            instance.setStatus(ProcessInstanceStatus.RUNNING);
        }
        instance.setUpdatedAt(Instant.now());

        producer.setStatus(ProcessStepStatus.READY);
        producer.setInput(new LinkedHashMap<>());
        producer.setOutput(new LinkedHashMap<>());
        producer.setError(new LinkedHashMap<>());
        producer.setDelegatedExecutionId(null);
        producer.setAvailableAt(null);
        producer.setDeadlineAt(null);
        producer.setStartedAt(null);
        producer.setCompletedAt(null);
        producer.setUpdatedAt(Instant.now());

        review.setStatus(ProcessStepStatus.PENDING);
        review.setInput(new LinkedHashMap<>());
        review.setOutput(new LinkedHashMap<>());
        review.setError(new LinkedHashMap<>());
        review.setDelegatedExecutionId(null);
        review.setAvailableAt(null);
        review.setDeadlineAt(null);
        review.setStartedAt(null);
        review.setCompletedAt(null);
        review.setUpdatedAt(Instant.now());

        steps.save(producer);
        steps.save(review);
        return toDomain(instances.saveAndFlush(instance));
    }

    @Override
    @Transactional
    public ProcessInstance failStep(
            UUID instanceId,
            String stepKey,
            Map<String,Object> error) {
        var step = requireStep(instanceId, stepKey);
        return terminalFail(instanceId, step, error);
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

    @Override
    @Transactional
    public ProcessInstance cancelInstance(UUID instanceId) {
        var instance = instances.findLockedById(instanceId)
                .orElseThrow(() -> new NoSuchElementException(
                        "Process instance not found: " + instanceId));
        var now = Instant.now();
        for (var step : instance.getSteps()) {
            if (step.getStatus() == ProcessStepStatus.PENDING
                    || step.getStatus() == ProcessStepStatus.READY
                    || step.getStatus() == ProcessStepStatus.RUNNING
                    || step.getStatus() == ProcessStepStatus.WAITING) {
                step.setStatus(ProcessStepStatus.CANCELLED);
                step.setCompletedAt(now);
                step.setUpdatedAt(now);
            }
        }
        instance.setStatus(ProcessInstanceStatus.CANCELLED);
        instance.setCompletedAt(now);
        instance.setUpdatedAt(now);
        return toDomain(instances.saveAndFlush(instance));
    }

    private ProcessInstance terminalFail(
            UUID instanceId,
            ProcessStepInstanceJpaEntity step,
            Map<String,Object> error) {
        var now = Instant.now();
        step.setStatus(ProcessStepStatus.FAILED);
        step.setError(new LinkedHashMap<>(error));
        step.setAvailableAt(null);
        step.setDeadlineAt(null);
        step.setCompletedAt(now);
        step.setUpdatedAt(now);
        steps.save(step);

        var instance = requireInstance(instanceId);
        instance.setStatus(ProcessInstanceStatus.FAILED);
        instance.setCompletedAt(now);
        instance.setUpdatedAt(now);
        return toDomain(instances.saveAndFlush(instance));
    }

    private ProcessInstanceJpaEntity requireInstance(UUID id) {
        return instances.findById(id)
                .orElseThrow(() -> new NoSuchElementException(
                        "Process instance not found: " + id));
    }

    private ProcessStepInstanceJpaEntity requireStep(UUID instanceId, String stepKey) {
        return steps.findLocked(instanceId, stepKey)
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
}
