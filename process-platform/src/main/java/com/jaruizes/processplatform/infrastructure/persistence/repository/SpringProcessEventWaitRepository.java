package com.jaruizes.processplatform.infrastructure.persistence.repository;

import com.jaruizes.processplatform.domain.model.ProcessEventWaitStatus;
import com.jaruizes.processplatform.infrastructure.persistence.entity.ProcessEventWaitJpaEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface SpringProcessEventWaitRepository
        extends JpaRepository<ProcessEventWaitJpaEntity, UUID> {
    Optional<ProcessEventWaitJpaEntity> findByProcessInstanceIdAndStepKey(UUID processInstanceId, String stepKey);
    List<ProcessEventWaitJpaEntity> findByEventTypeAndCorrelationIdAndStatus(
            String eventType, String correlationId, ProcessEventWaitStatus status);
    List<ProcessEventWaitJpaEntity> findByProcessInstanceIdAndStatus(
            UUID processInstanceId, ProcessEventWaitStatus status);
}
