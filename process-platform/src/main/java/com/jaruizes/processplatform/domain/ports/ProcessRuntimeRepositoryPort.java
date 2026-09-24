package com.jaruizes.processplatform.domain.ports;

import com.jaruizes.processplatform.domain.model.*;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

public interface ProcessRuntimeRepositoryPort {
    Optional<ProcessInstance> findInstance(UUID instanceId);
    Optional<ProcessInstance> findByDelegatedExecutionId(UUID executionId);
    List<ProcessInstance> findRunnableInstances();

    ProcessInstance updateInstanceStatus(UUID instanceId, ProcessInstanceStatus status);
    boolean markReady(UUID instanceId, String stepKey);
    int claimReady(UUID instanceId, String stepKey, Map<String,Object> input, Long timeoutSeconds);
    boolean resetRunningStep(UUID instanceId, String stepKey, int expectedAttempt);
    boolean retryStep(UUID instanceId, String stepKey, int expectedAttempt, Map<String,Object> error, Instant availableAt);
    boolean waitStep(UUID instanceId, String stepKey, int expectedAttempt);
    ProcessInstance skipStep(UUID instanceId, String stepKey, Map<String,Object> output);
    boolean delegateAgent(UUID instanceId, String stepKey, int expectedAttempt, ExecutionCommand command);
    boolean completeStep(UUID instanceId, String stepKey, int expectedAttempt, Map<String,Object> output);
    boolean failAttempt(UUID instanceId, String stepKey, int expectedAttempt, Map<String,Object> error);
    ProcessInstance failStep(UUID instanceId, String stepKey, Map<String,Object> error);
    ProcessInstance completeInstance(UUID instanceId);
    ProcessInstance failInstance(UUID instanceId);
    ProcessInstance cancelInstance(UUID instanceId);
}
