package com.jaruizes.processplatform.infrastructure.persistence.entity;

import com.jaruizes.processplatform.domain.model.ProcessEventWaitStatus;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name="process_event_waits")
public class ProcessEventWaitJpaEntity {
    @Id private UUID id;
    @Column(name="process_instance_id", nullable=false) private UUID processInstanceId;
    @Column(name="step_key", nullable=false, length=200) private String stepKey;
    @Column(name="event_type", nullable=false, length=300) private String eventType;
    @Column(name="correlation_id", nullable=false, length=300) private String correlationId;
    @Enumerated(EnumType.STRING) @Column(nullable=false, length=30) private ProcessEventWaitStatus status;
    @JdbcTypeCode(SqlTypes.JSON) @Column(nullable=false, columnDefinition="jsonb")
    private Map<String,Object> payload = new LinkedHashMap<>();
    @Column(name="created_at", nullable=false) private Instant createdAt;
    @Column(name="consumed_at") private Instant consumedAt;

    public ProcessEventWaitJpaEntity() {}
    public UUID getId(){return id;} public void setId(UUID v){id=v;}
    public UUID getProcessInstanceId(){return processInstanceId;} public void setProcessInstanceId(UUID v){processInstanceId=v;}
    public String getStepKey(){return stepKey;} public void setStepKey(String v){stepKey=v;}
    public String getEventType(){return eventType;} public void setEventType(String v){eventType=v;}
    public String getCorrelationId(){return correlationId;} public void setCorrelationId(String v){correlationId=v;}
    public ProcessEventWaitStatus getStatus(){return status;} public void setStatus(ProcessEventWaitStatus v){status=v;}
    public Map<String,Object> getPayload(){return payload;} public void setPayload(Map<String,Object> v){payload=v;}
    public Instant getCreatedAt(){return createdAt;} public void setCreatedAt(Instant v){createdAt=v;}
    public Instant getConsumedAt(){return consumedAt;} public void setConsumedAt(Instant v){consumedAt=v;}
}
