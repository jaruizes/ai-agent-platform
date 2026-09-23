package com.jaruizes.processplatform.infrastructure.persistence.repository;

import com.jaruizes.processplatform.infrastructure.persistence.entity.ProcessStepInstanceJpaEntity;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;

import java.util.Optional;
import java.util.UUID;

public interface SpringProcessStepInstanceRepository
        extends JpaRepository<ProcessStepInstanceJpaEntity, UUID> {

    Optional<ProcessStepInstanceJpaEntity> findByDelegatedExecutionId(UUID executionId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    Optional<ProcessStepInstanceJpaEntity>
    findByInstanceIdAndStepKey(UUID instanceId, String stepKey);
}
