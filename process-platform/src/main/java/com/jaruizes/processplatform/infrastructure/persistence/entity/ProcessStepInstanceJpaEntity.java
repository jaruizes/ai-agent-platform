package com.jaruizes.processplatform.infrastructure.persistence.entity;

import com.jaruizes.processplatform.domain.model.ProcessStepStatus;
import com.jaruizes.processplatform.domain.model.ProcessStepType;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.*;

@Entity
@Table(name = "process_step_instances",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_process_step_instance_key",
                columnNames = {"process_instance_id", "step_key"}))
public class ProcessStepInstanceJpaEntity {

    @Id
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "process_instance_id", nullable = false)
    private ProcessInstanceJpaEntity instance;

    @Column(name = "step_definition_id", nullable = false)
    private UUID stepDefinitionId;

    @Column(name = "step_key", nullable = false, length = 200)
    private String stepKey;

    @Enumerated(EnumType.STRING)
    @Column(name = "step_type", nullable = false, length = 50)
    private ProcessStepType type;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private ProcessStepStatus status;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private Map<String,Object> input = new LinkedHashMap<>();

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private Map<String,Object> output = new LinkedHashMap<>();

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private Map<String,Object> error = new LinkedHashMap<>();

    @Column(name = "delegated_execution_id")
    private UUID delegatedExecutionId;

    @Column(name = "attempt_count", nullable = false)
    private int attemptCount;

    @Column(name = "available_at")
    private Instant availableAt;

    @Column(name = "deadline_at")
    private Instant deadlineAt;

    @Column(name = "started_at")
    private Instant startedAt;

    @Column(name = "completed_at")
    private Instant completedAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    public ProcessStepInstanceJpaEntity() {}

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public ProcessInstanceJpaEntity getInstance() { return instance; }
    public void setInstance(ProcessInstanceJpaEntity instance) { this.instance = instance; }
    public UUID getStepDefinitionId() { return stepDefinitionId; }
    public void setStepDefinitionId(UUID stepDefinitionId) { this.stepDefinitionId = stepDefinitionId; }
    public String getStepKey() { return stepKey; }
    public void setStepKey(String stepKey) { this.stepKey = stepKey; }
    public ProcessStepType getType() { return type; }
    public void setType(ProcessStepType type) { this.type = type; }
    public ProcessStepStatus getStatus() { return status; }
    public void setStatus(ProcessStepStatus status) { this.status = status; }
    public Map<String,Object> getInput() { return input; }
    public void setInput(Map<String,Object> input) { this.input = input; }
    public Map<String,Object> getOutput() { return output; }
    public void setOutput(Map<String,Object> output) { this.output = output; }
    public Map<String,Object> getError() { return error; }
    public void setError(Map<String,Object> error) { this.error = error; }
    public UUID getDelegatedExecutionId() { return delegatedExecutionId; }
    public void setDelegatedExecutionId(UUID delegatedExecutionId) { this.delegatedExecutionId = delegatedExecutionId; }
    public int getAttemptCount() { return attemptCount; }
    public void setAttemptCount(int attemptCount) { this.attemptCount = attemptCount; }
    public Instant getAvailableAt() { return availableAt; }
    public void setAvailableAt(Instant availableAt) { this.availableAt = availableAt; }
    public Instant getDeadlineAt() { return deadlineAt; }
    public void setDeadlineAt(Instant deadlineAt) { this.deadlineAt = deadlineAt; }
    public Instant getStartedAt() { return startedAt; }
    public void setStartedAt(Instant startedAt) { this.startedAt = startedAt; }
    public Instant getCompletedAt() { return completedAt; }
    public void setCompletedAt(Instant completedAt) { this.completedAt = completedAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
}
