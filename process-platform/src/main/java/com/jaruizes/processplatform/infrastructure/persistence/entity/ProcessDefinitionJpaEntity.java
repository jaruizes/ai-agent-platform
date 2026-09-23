package com.jaruizes.processplatform.infrastructure.persistence.entity;

import com.jaruizes.processplatform.domain.model.ProcessDefinitionStatus;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.*;

@Entity
@Table(name = "process_definitions",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_process_definition_key_version",
                columnNames = {"definition_key", "version"}))
public class ProcessDefinitionJpaEntity {

    @Id
    private UUID id;

    @Column(name = "definition_key", nullable = false, length = 200)
    private String definitionKey;

    @Column(nullable = false, length = 300)
    private String name;

    @Column(nullable = false)
    private String description;

    @Column(nullable = false)
    private int version;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 30)
    private ProcessDefinitionStatus status;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "input_schema", nullable = false, columnDefinition = "jsonb")
    private Map<String,Object> inputSchema = new LinkedHashMap<>();

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "output_schema", nullable = false, columnDefinition = "jsonb")
    private Map<String,Object> outputSchema = new LinkedHashMap<>();

    @OneToMany(mappedBy = "definition", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("stepKey ASC")
    private List<ProcessStepDefinitionJpaEntity> steps = new ArrayList<>();

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @Column(name = "activated_at")
    private Instant activatedAt;

    protected ProcessDefinitionJpaEntity() {}

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public String getDefinitionKey() { return definitionKey; }
    public void setDefinitionKey(String definitionKey) { this.definitionKey = definitionKey; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public int getVersion() { return version; }
    public void setVersion(int version) { this.version = version; }
    public ProcessDefinitionStatus getStatus() { return status; }
    public void setStatus(ProcessDefinitionStatus status) { this.status = status; }
    public Map<String,Object> getInputSchema() { return inputSchema; }
    public void setInputSchema(Map<String,Object> inputSchema) { this.inputSchema = inputSchema; }
    public Map<String,Object> getOutputSchema() { return outputSchema; }
    public void setOutputSchema(Map<String,Object> outputSchema) { this.outputSchema = outputSchema; }
    public List<ProcessStepDefinitionJpaEntity> getSteps() { return steps; }
    public void replaceSteps(List<ProcessStepDefinitionJpaEntity> value) {
        steps.clear();
        value.forEach(step -> {
            step.setDefinition(this);
            steps.add(step);
        });
    }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
    public Instant getActivatedAt() { return activatedAt; }
    public void setActivatedAt(Instant activatedAt) { this.activatedAt = activatedAt; }
}
