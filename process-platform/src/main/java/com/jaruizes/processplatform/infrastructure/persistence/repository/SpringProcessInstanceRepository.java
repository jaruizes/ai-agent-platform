package com.jaruizes.processplatform.infrastructure.persistence.repository;

import com.jaruizes.processplatform.infrastructure.persistence.entity.ProcessInstanceJpaEntity;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.UUID;

public interface SpringProcessInstanceRepository
        extends JpaRepository<ProcessInstanceJpaEntity, UUID> {

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select p from ProcessInstanceJpaEntity p where p.id = :id")
    java.util.Optional<ProcessInstanceJpaEntity> findLockedById(@Param("id") UUID id);
}
