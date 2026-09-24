package com.jaruizes.processplatform.infrastructure.persistence.repository;

import com.jaruizes.processplatform.domain.model.HumanTaskStatus;
import com.jaruizes.processplatform.infrastructure.persistence.entity.HumanTaskJpaEntity;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface SpringHumanTaskRepository extends JpaRepository<HumanTaskJpaEntity, UUID> {
    Optional<HumanTaskJpaEntity> findByProcessInstanceIdAndStepKey(UUID processInstanceId, String stepKey);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select h from HumanTaskJpaEntity h where h.id = :id")
    Optional<HumanTaskJpaEntity> findLockedById(@Param("id") UUID id);
    List<HumanTaskJpaEntity> findByStatusOrderByCreatedAtAsc(HumanTaskStatus status);
    List<HumanTaskJpaEntity> findByProcessInstanceIdAndStatus(UUID processInstanceId, HumanTaskStatus status);
}
