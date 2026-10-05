package com.jaruizes.processplatform.domain.ports;

import com.jaruizes.processplatform.domain.model.HumanTask;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface HumanTaskRepositoryPort {
    HumanTask createIfAbsent(HumanTask task);
    Optional<HumanTask> findById(UUID id);
    List<HumanTask> findAll();
    List<HumanTask> findPending();
    HumanTask complete(UUID id, String decision, java.util.Map<String,Object> result);
    void cancelPendingForInstance(UUID processInstanceId);
}
