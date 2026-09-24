package com.jaruizes.processplatform.infrastructure.persistence.entity;

import com.jaruizes.processplatform.domain.model.ProcessServiceStatus;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "process_service_definitions")
public class ProcessServiceDefinitionJpaEntity {
    @Id
    private UUID id;
    @Column(name="service_key", nullable=false, length=200)
    private String serviceKey;
    @Column(nullable=false, length=300)
    private String name;
    @Column(nullable=false, columnDefinition="text")
    private String description;
    @Column(nullable=false)
    private int version;
    @Enumerated(EnumType.STRING)
    @Column(nullable=false, length=30)
    private ProcessServiceStatus status;
    @Column(name="implementation_key", nullable=false, length=200)
    private String implementationKey;
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name="input_schema", nullable=false, columnDefinition="jsonb")
    private Map<String,Object> inputSchema = new LinkedHashMap<>();
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name="output_schema", nullable=false, columnDefinition="jsonb")
    private Map<String,Object> outputSchema = new LinkedHashMap<>();
    @Column(name="created_at", nullable=false)
    private Instant createdAt;
    @Column(name="updated_at", nullable=false)
    private Instant updatedAt;
    @Column(name="activated_at")
    private Instant activatedAt;

    public ProcessServiceDefinitionJpaEntity() {}
    public UUID getId(){return id;} public void setId(UUID v){id=v;}
    public String getServiceKey(){return serviceKey;} public void setServiceKey(String v){serviceKey=v;}
    public String getName(){return name;} public void setName(String v){name=v;}
    public String getDescription(){return description;} public void setDescription(String v){description=v;}
    public int getVersion(){return version;} public void setVersion(int v){version=v;}
    public ProcessServiceStatus getStatus(){return status;} public void setStatus(ProcessServiceStatus v){status=v;}
    public String getImplementationKey(){return implementationKey;} public void setImplementationKey(String v){implementationKey=v;}
    public Map<String,Object> getInputSchema(){return inputSchema;} public void setInputSchema(Map<String,Object> v){inputSchema=v;}
    public Map<String,Object> getOutputSchema(){return outputSchema;} public void setOutputSchema(Map<String,Object> v){outputSchema=v;}
    public Instant getCreatedAt(){return createdAt;} public void setCreatedAt(Instant v){createdAt=v;}
    public Instant getUpdatedAt(){return updatedAt;} public void setUpdatedAt(Instant v){updatedAt=v;}
    public Instant getActivatedAt(){return activatedAt;} public void setActivatedAt(Instant v){activatedAt=v;}
}
