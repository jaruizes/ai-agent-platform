package com.jaruizes.processplatform.infrastructure.persistence.entity;

import com.jaruizes.processplatform.domain.model.HumanTaskStatus;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name="process_human_tasks")
public class HumanTaskJpaEntity {
    @Id private UUID id;
    @Column(name="process_instance_id", nullable=false) private UUID processInstanceId;
    @Column(name="step_key", nullable=false, length=200) private String stepKey;
    @Column(nullable=false, length=500) private String title;
    @Column(nullable=false, columnDefinition="text") private String description;
    @JdbcTypeCode(SqlTypes.JSON) @Column(nullable=false, columnDefinition="jsonb")
    private Map<String,Object> payload = new LinkedHashMap<>();
    @Enumerated(EnumType.STRING) @Column(nullable=false, length=30) private HumanTaskStatus status;
    @Column(length=100) private String decision;
    @JdbcTypeCode(SqlTypes.JSON) @Column(nullable=false, columnDefinition="jsonb")
    private Map<String,Object> result = new LinkedHashMap<>();
    @Column(name="created_at", nullable=false) private Instant createdAt;
    @Column(name="completed_at") private Instant completedAt;

    public HumanTaskJpaEntity() {}
    public UUID getId(){return id;} public void setId(UUID v){id=v;}
    public UUID getProcessInstanceId(){return processInstanceId;} public void setProcessInstanceId(UUID v){processInstanceId=v;}
    public String getStepKey(){return stepKey;} public void setStepKey(String v){stepKey=v;}
    public String getTitle(){return title;} public void setTitle(String v){title=v;}
    public String getDescription(){return description;} public void setDescription(String v){description=v;}
    public Map<String,Object> getPayload(){return payload;} public void setPayload(Map<String,Object> v){payload=v;}
    public HumanTaskStatus getStatus(){return status;} public void setStatus(HumanTaskStatus v){status=v;}
    public String getDecision(){return decision;} public void setDecision(String v){decision=v;}
    public Map<String,Object> getResult(){return result;} public void setResult(Map<String,Object> v){result=v;}
    public Instant getCreatedAt(){return createdAt;} public void setCreatedAt(Instant v){createdAt=v;}
    public Instant getCompletedAt(){return completedAt;} public void setCompletedAt(Instant v){completedAt=v;}
}
