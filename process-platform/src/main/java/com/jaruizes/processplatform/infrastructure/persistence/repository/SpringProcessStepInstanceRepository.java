package com.jaruizes.processplatform.infrastructure.persistence.repository;

import com.jaruizes.processplatform.infrastructure.persistence.entity.ProcessStepInstanceJpaEntity;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;
import java.util.UUID;

public interface SpringProcessStepInstanceRepository
        extends JpaRepository<ProcessStepInstanceJpaEntity, UUID> {

    Optional<ProcessStepInstanceJpaEntity> findByDelegatedExecutionId(UUID executionId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("""
        select s from ProcessStepInstanceJpaEntity s
        where s.instance.id = :instanceId and s.stepKey = :stepKey
        """)
    Optional<ProcessStepInstanceJpaEntity> findLocked(
            @Param("instanceId") UUID instanceId,
            @Param("stepKey") String stepKey);
}
