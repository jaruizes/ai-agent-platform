package com.jaruizes.processplatform.infrastructure.persistence.repository;

import com.jaruizes.processplatform.infrastructure.persistence.entity.ProcessInstanceJpaEntity;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;

import java.util.UUID;

public interface SpringProcessInstanceRepository
        extends JpaRepository<ProcessInstanceJpaEntity, UUID> {

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    java.util.Optional<ProcessInstanceJpaEntity> findLockedById(UUID id);
}
