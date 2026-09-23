package com.jaruizes.processplatform.infrastructure.persistence.entity;

import com.jaruizes.processplatform.domain.model.ProcessStepType;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.util.*;

@Entity
@Table(name = "process_step_definitions",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_process_step_definition_key",
                columnNames = {"process_definition_id", "step_key"}))
public class ProcessStepDefinitionJpaEntity {

    @Id
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "process_definition_id", nullable = false)
    private ProcessDefinitionJpaEntity definition;

    @Column(name = "step_key", nullable = false, length = 200)
    private String stepKey;

    @Column(nullable = false, length = 300)
    private String name;

    @Column(nullable = false)
    private String description;

    @Enumerated(EnumType.STRING)
    @Column(name = "step_type", nullable = false, length = 50)
    private ProcessStepType type;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "depends_on", nullable = false, columnDefinition = "jsonb")
    private List<String> dependsOn = new ArrayList<>();

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "input_schema", nullable = false, columnDefinition = "jsonb")
    private Map<String,Object> inputSchema = new LinkedHashMap<>();

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "output_schema", nullable = false, columnDefinition = "jsonb")
    private Map<String,Object> outputSchema = new LinkedHashMap<>();

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private Map<String,Object> configuration = new LinkedHashMap<>();

    public ProcessStepDefinitionJpaEntity() {}

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public ProcessDefinitionJpaEntity getDefinition() { return definition; }
    public void setDefinition(ProcessDefinitionJpaEntity definition) { this.definition = definition; }
    public String getStepKey() { return stepKey; }
    public void setStepKey(String stepKey) { this.stepKey = stepKey; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public ProcessStepType getType() { return type; }
    public void setType(ProcessStepType type) { this.type = type; }
    public List<String> getDependsOn() { return dependsOn; }
    public void setDependsOn(List<String> dependsOn) { this.dependsOn = dependsOn; }
    public Map<String,Object> getInputSchema() { return inputSchema; }
    public void setInputSchema(Map<String,Object> inputSchema) { this.inputSchema = inputSchema; }
    public Map<String,Object> getOutputSchema() { return outputSchema; }
    public void setOutputSchema(Map<String,Object> outputSchema) { this.outputSchema = outputSchema; }
    public Map<String,Object> getConfiguration() { return configuration; }
    public void setConfiguration(Map<String,Object> configuration) { this.configuration = configuration; }
}
