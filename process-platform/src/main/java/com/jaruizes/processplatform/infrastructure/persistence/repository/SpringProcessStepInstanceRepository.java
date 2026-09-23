package com.jaruizes.processplatform.infrastructure.persistence.repository;

import com.jaruizes.processplatform.infrastructure.persistence.entity.ProcessStepInstanceJpaEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface SpringProcessStepInstanceRepository
        extends JpaRepository<ProcessStepInstanceJpaEntity, UUID> {

    Optional<ProcessStepInstanceJpaEntity> findByDelegatedExecutionId(UUID executionId);
}
