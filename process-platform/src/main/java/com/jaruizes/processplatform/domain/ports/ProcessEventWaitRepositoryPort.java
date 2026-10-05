package com.jaruizes.processplatform.domain.ports;

import com.jaruizes.processplatform.domain.model.ProcessEventWait;

import java.util.List;
import java.util.UUID;

public interface ProcessEventWaitRepositoryPort {
    ProcessEventWait createIfAbsent(ProcessEventWait wait);
    List<ProcessEventWait> findWaiting(String eventType, String correlationId);
    ProcessEventWait consume(UUID id, java.util.Map<String,Object> payload);
    void cancelWaitingForInstance(UUID processInstanceId);
}
