package com.jaruizes.processplatform.infrastructure.persistence.entity;

import com.jaruizes.processplatform.domain.model.ProcessInstanceStatus;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.*;

@Entity
@Table(name = "process_instances")
public class ProcessInstanceJpaEntity {

    @Id
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "process_definition_id", nullable = false)
    private ProcessDefinitionJpaEntity definition;

    @Column(name = "definition_key", nullable = false, length = 200)
    private String definitionKey;

    @Column(name = "definition_version", nullable = false)
    private int definitionVersion;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private ProcessInstanceStatus status;

    @Column(name = "correlation_id", nullable = false, length = 200)
    private String correlationId;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private Map<String,Object> input = new LinkedHashMap<>();

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "process_context", nullable = false, columnDefinition = "jsonb")
    private Map<String,Object> context = new LinkedHashMap<>();

    @OneToMany(mappedBy = "instance", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("stepKey ASC")
    private List<ProcessStepInstanceJpaEntity> steps = new ArrayList<>();

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @Column(name = "completed_at")
    private Instant completedAt;

    protected ProcessInstanceJpaEntity() {}

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public ProcessDefinitionJpaEntity getDefinition() { return definition; }
    public void setDefinition(ProcessDefinitionJpaEntity definition) { this.definition = definition; }
    public String getDefinitionKey() { return definitionKey; }
    public void setDefinitionKey(String definitionKey) { this.definitionKey = definitionKey; }
    public int getDefinitionVersion() { return definitionVersion; }
    public void setDefinitionVersion(int definitionVersion) { this.definitionVersion = definitionVersion; }
    public ProcessInstanceStatus getStatus() { return status; }
    public void setStatus(ProcessInstanceStatus status) { this.status = status; }
    public String getCorrelationId() { return correlationId; }
    public void setCorrelationId(String correlationId) { this.correlationId = correlationId; }
    public Map<String,Object> getInput() { return input; }
    public void setInput(Map<String,Object> input) { this.input = input; }
    public Map<String,Object> getContext() { return context; }
    public void setContext(Map<String,Object> context) { this.context = context; }
    public List<ProcessStepInstanceJpaEntity> getSteps() { return steps; }
    public void replaceSteps(List<ProcessStepInstanceJpaEntity> value) {
        steps.clear();
        value.forEach(step -> {
            step.setInstance(this);
            steps.add(step);
        });
    }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
    public Instant getCompletedAt() { return completedAt; }
    public void setCompletedAt(Instant completedAt) { this.completedAt = completedAt; }
}
