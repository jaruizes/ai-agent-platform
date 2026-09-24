package com.jaruizes.processplatform.infrastructure.persistence.repository;

import com.jaruizes.processplatform.domain.model.HumanTaskStatus;
import com.jaruizes.processplatform.infrastructure.persistence.entity.HumanTaskJpaEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface SpringHumanTaskRepository extends JpaRepository<HumanTaskJpaEntity, UUID> {
    Optional<HumanTaskJpaEntity> findByProcessInstanceIdAndStepKey(UUID processInstanceId, String stepKey);
    List<HumanTaskJpaEntity> findByStatusOrderByCreatedAtAsc(HumanTaskStatus status);
    List<HumanTaskJpaEntity> findByProcessInstanceIdAndStatus(UUID processInstanceId, HumanTaskStatus status);
}
