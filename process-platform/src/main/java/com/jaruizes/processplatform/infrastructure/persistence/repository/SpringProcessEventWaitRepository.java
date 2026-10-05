package com.jaruizes.processplatform.infrastructure.persistence.repository;

import com.jaruizes.processplatform.domain.model.ProcessEventWaitStatus;
import com.jaruizes.processplatform.infrastructure.persistence.entity.ProcessEventWaitJpaEntity;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface SpringProcessEventWaitRepository
        extends JpaRepository<ProcessEventWaitJpaEntity, UUID> {
    Optional<ProcessEventWaitJpaEntity> findByProcessInstanceIdAndStepKey(UUID processInstanceId, String stepKey);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select w from ProcessEventWaitJpaEntity w where w.id = :id")
    Optional<ProcessEventWaitJpaEntity> findLockedById(@Param("id") UUID id);
    List<ProcessEventWaitJpaEntity> findByEventTypeAndCorrelationIdAndStatus(
            String eventType, String correlationId, ProcessEventWaitStatus status);
    List<ProcessEventWaitJpaEntity> findByProcessInstanceIdAndStatus(
            UUID processInstanceId, ProcessEventWaitStatus status);
}
