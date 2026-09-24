package com.jaruizes.processplatform.business;

import com.jaruizes.processplatform.domain.model.*;
import com.jaruizes.processplatform.domain.ports.*;
import jakarta.annotation.PreDestroy;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.time.Instant;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@Service
public class ProcessRuntimeService {

    private final ProcessRuntimeRepositoryPort runtime;
    private final ProcessDefinitionRepositoryPort definitions;
    private final ProcessContractValidator contracts;
    private final ProcessServiceCatalogService services;
    private final ProcessDecisionEvaluator decisions;
    private final AgentPlatformIntegrationService agentPlatform;
    private final HumanTaskRepositoryPort humanTasks;
    private final ProcessEventWaitRepositoryPort eventWaits;
    private final long staleStepSeconds;
    private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();

    public ProcessRuntimeService(
            ProcessRuntimeRepositoryPort runtime,
            ProcessDefinitionRepositoryPort definitions,
            ProcessContractValidator contracts,
            ProcessServiceCatalogService services,
            ProcessDecisionEvaluator decisions,
            AgentPlatformIntegrationService agentPlatform,
            HumanTaskRepositoryPort humanTasks,
            ProcessEventWaitRepositoryPort eventWaits,
            @Value("${process.runtime.step-stale-seconds:60}") long staleStepSeconds) {
        this.runtime = runtime;
        this.definitions = definitions;
        this.contracts = contracts;
        this.services = services;
        this.decisions = decisions;
        this.agentPlatform = agentPlatform;
        this.humanTasks = humanTasks;
        this.eventWaits = eventWaits;
        this.staleStepSeconds = Math.max(1, staleStepSeconds);
    }

    public ProcessInstance start(UUID instanceId) {
        var instance = requireInstance(instanceId);
        if (instance.status() == ProcessInstanceStatus.PAUSED) {
            throw new IllegalStateException("Use resume for a PAUSED process instance");
        }
        if (isTerminal(instance.status())) {
            throw new IllegalStateException("Process instance is terminal: " + instance.status());
        }

        var definition = requireDefinition(instance.definitionId());
        contracts.validate("process.input", definition.inputSchema(), instance.input());

        var running = runtime.updateInstanceStatus(instanceId, ProcessInstanceStatus.RUNNING);
        scheduleAdvance(instanceId);
        return running;
    }

    public ProcessInstance pause(UUID instanceId) {
        var instance = requireInstance(instanceId);
        if (instance.status() != ProcessInstanceStatus.RUNNING
                && instance.status() != ProcessInstanceStatus.WAITING) {
            throw new IllegalStateException(
                    "Only RUNNING or WAITING process instances can be paused");
        }
        return runtime.updateInstanceStatus(instanceId, ProcessInstanceStatus.PAUSED);
    }

    public ProcessInstance resume(UUID instanceId) {
        var instance = requireInstance(instanceId);
        if (instance.status() != ProcessInstanceStatus.PAUSED) {
            throw new IllegalStateException("Only PAUSED process instances can be resumed");
        }
        var resumed = runtime.updateInstanceStatus(instanceId, ProcessInstanceStatus.RUNNING);
        scheduleAdvance(instanceId);
        return resumed;
    }

    public ProcessInstance cancel(UUID instanceId) {
        var instance = requireInstance(instanceId);
        if (instance.status() == ProcessInstanceStatus.CANCELLED) return instance;
        if (instance.status() == ProcessInstanceStatus.COMPLETED
                || instance.status() == ProcessInstanceStatus.FAILED) {
            throw new IllegalStateException("Process instance is terminal: " + instance.status());
        }
        humanTasks.cancelPendingForInstance(instanceId);
        eventWaits.cancelWaitingForInstance(instanceId);
        return runtime.cancelInstance(instanceId);
    }

    public ProcessInstance get(UUID instanceId) {
        return requireInstance(instanceId);
    }

    public List<HumanTask> humanTasks(boolean pendingOnly) {
        return pendingOnly ? humanTasks.findPending() : humanTasks.findAll();
    }

    @Transactional
    public HumanTask completeHumanTask(
            UUID taskId,
            String decision,
            Map<String,Object> result) {
        if (decision == null || decision.isBlank()) {
            throw new IllegalArgumentException("decision is required");
        }
        var task = humanTasks.findById(taskId)
                .orElseThrow(() -> new NoSuchElementException("Human task not found: " + taskId));
        if (task.status() != HumanTaskStatus.PENDING) return task;

        var instance = requireInstance(task.processInstanceId());
        if (instance.status() == ProcessInstanceStatus.CANCELLED) {
            throw new IllegalStateException("Process instance is cancelled");
        }
        var definition = requireDefinition(instance.definitionId());
        var stepDefinition = byKey(definition.steps()).get(task.stepKey());
        if (stepDefinition == null) {
            throw new IllegalStateException("Human task step definition not found: " + task.stepKey());
        }
        var stepInstance = instance.steps().stream()
                .filter(step -> step.stepKey().equals(task.stepKey()))
                .findFirst()
                .orElseThrow(() -> new IllegalStateException(
                        "Human task step instance not found: " + task.stepKey()));

        var review = reviewPolicy(stepDefinition.configuration());
        if (review != null) {
            if (decision.equalsIgnoreCase(review.repeatDecision())) {
                if (task.iteration() >= review.maxIterations()) {
                    throw new IllegalStateException(
                            "Review iteration limit reached (%d). Approve or cancel the process."
                                    .formatted(review.maxIterations()));
                }

                var completed = humanTasks.complete(taskId, decision, safeMap(result));
                var feedback = new LinkedHashMap<String,Object>();
                feedback.put("decision", decision);
                feedback.put("result", safeMap(result));
                feedback.put("humanTaskId", taskId.toString());
                feedback.put("iteration", task.iteration());

                runtime.repeatReviewedStep(
                        task.processInstanceId(),
                        review.repeatStep(),
                        task.stepKey(),
                        stepInstance.attemptCount(),
                        feedback);
                scheduleAdvance(task.processInstanceId());
                return completed;
            }

            if (!decision.equalsIgnoreCase(review.approveDecision())) {
                throw new IllegalArgumentException(
                        "Review decision must be '%s' or '%s'"
                                .formatted(review.approveDecision(), review.repeatDecision()));
            }
        }

        var completed = humanTasks.complete(taskId, decision, safeMap(result));
        var output = new LinkedHashMap<String,Object>();
        output.put("decision", decision);
        output.put("result", safeMap(result));
        output.put("iteration", task.iteration());
        completeWaitingStep(task.processInstanceId(), task.stepKey(), output);
        return completed;
    }

    public int signalEvent(
            String eventType,
            String correlationId,
            Map<String,Object> payload) {
        if (eventType == null || eventType.isBlank()) {
            throw new IllegalArgumentException("eventType is required");
        }
        if (correlationId == null || correlationId.isBlank()) {
            throw new IllegalArgumentException("correlationId is required");
        }

        var waits = eventWaits.findWaiting(eventType, correlationId);
        for (var wait : waits) {
            eventWaits.consume(wait.id(), safeMap(payload));
            var output = new LinkedHashMap<String,Object>();
            output.put("eventType", eventType);
            output.put("correlationId", correlationId);
            output.put("payload", safeMap(payload));
            completeWaitingStep(wait.processInstanceId(), wait.stepKey(), output);
        }
        return waits.size();
    }

    @EventListener
    public void onAgentExecutionEvent(AgentExecutionEventReceived received) {
        var event = received.event();
        if (event == null || !event.isTerminal()
                || event.execution() == null
                || event.execution().executionId() == null) {
            return;
        }

        runtime.findByDelegatedExecutionId(event.execution().executionId())
                .filter(instance -> !isTerminal(instance.status()))
                .ifPresent(instance -> executor.submit(
                        () -> handleTerminalAgentEvent(instance, event)));
    }

    @Scheduled(fixedDelayString = "${process.runtime.recovery-delay-ms:2000}")
    public void recoverRunnableInstances() {
        var now = Instant.now();
        var staleCutoff = now.minusSeconds(staleStepSeconds);

        for (var instance : runtime.findRunnableInstances()) {
            var definition = requireDefinition(instance.definitionId());
            var defs = byKey(definition.steps());

            for (var step : instance.steps()) {
                var stepDefinition = defs.get(step.stepKey());
                if (stepDefinition == null) continue;

                if (step.status() == ProcessStepStatus.WAITING
                        && step.deadlineAt() != null
                        && !step.deadlineAt().isAfter(now)) {
                    handleStepFailure(
                            instance.id(),
                            stepDefinition,
                            step.attemptCount(),
                            "STEP_TIMEOUT",
                            "Step timed out while waiting");
                    continue;
                }

                if (step.status() == ProcessStepStatus.RUNNING) {
                    var configuredTimeoutExpired = step.deadlineAt() != null
                            && !step.deadlineAt().isAfter(now);
                    var staleWithoutDeadline = step.deadlineAt() == null
                            && step.startedAt() != null
                            && step.startedAt().isBefore(staleCutoff);

                    if (configuredTimeoutExpired) {
                        handleStepFailure(
                                instance.id(),
                                stepDefinition,
                                step.attemptCount(),
                                "STEP_TIMEOUT",
                                "Step execution exceeded its timeout");
                    } else if (staleWithoutDeadline
                            && (step.type() == ProcessStepType.SERVICE
                                || step.type() == ProcessStepType.AGENTIC_EXECUTION
                                || step.type() == ProcessStepType.DECISION)) {
                        runtime.resetRunningStep(instance.id(), step.stepKey(), step.attemptCount());
                    }
                }
            }
            scheduleAdvance(instance.id());
        }
    }

    private void advance(UUID instanceId) {
        var instance = requireInstance(instanceId);
        if (instance.status() == ProcessInstanceStatus.PAUSED || isTerminal(instance.status())) {
            return;
        }

        var definition = requireDefinition(instance.definitionId());
        var stepInstances = instance.steps().stream()
                .collect(java.util.stream.Collectors.toMap(
                        ProcessStepInstance::stepKey, step -> step));

        if (stepInstances.values().stream()
                .anyMatch(step -> step.status() == ProcessStepStatus.FAILED)) {
            runtime.failInstance(instanceId);
            return;
        }

        if (!stepInstances.isEmpty()
                && stepInstances.values().stream()
                .allMatch(step -> step.status() == ProcessStepStatus.COMPLETED
                        || step.status() == ProcessStepStatus.SKIPPED)) {
            try {
                contracts.validate("process.output", definition.outputSchema(), instance.context());
                runtime.completeInstance(instanceId);
            } catch (Exception outputContractError) {
                runtime.failInstance(instanceId);
            }
            return;
        }

        var ready = new LinkedHashSet<String>();
        var now = Instant.now();

        stepInstances.values().stream()
                .filter(step -> step.status() == ProcessStepStatus.READY)
                .filter(step -> step.availableAt() == null || !step.availableAt().isAfter(now))
                .map(ProcessStepInstance::stepKey)
                .forEach(ready::add);

        boolean skippedAny = false;
        for (var stepDefinition : definition.steps()) {
            var step = stepInstances.get(stepDefinition.stepKey());
            if (step == null || step.status() != ProcessStepStatus.PENDING) continue;

            var dependencyStates = stepDefinition.dependsOn().stream()
                    .map(stepInstances::get)
                    .filter(Objects::nonNull)
                    .map(ProcessStepInstance::status)
                    .toList();

            var dependenciesTerminal = dependencyStates.size() == stepDefinition.dependsOn().size()
                    && dependencyStates.stream().allMatch(status ->
                        status == ProcessStepStatus.COMPLETED
                                || status == ProcessStepStatus.SKIPPED);
            if (!dependenciesTerminal) continue;

            if (!dependencyStates.isEmpty()
                    && dependencyStates.stream().allMatch(
                        status -> status == ProcessStepStatus.SKIPPED)) {
                runtime.skipStep(
                        instanceId,
                        stepDefinition.stepKey(),
                        Map.of("reason", "all-dependencies-skipped"));
                skippedAny = true;
                continue;
            }

            if (!conditionMatches(instance.context(), stepDefinition.configuration())) {
                runtime.skipStep(
                        instanceId,
                        stepDefinition.stepKey(),
                        Map.of("reason", "condition-not-matched"));
                skippedAny = true;
                continue;
            }

            if (runtime.markReady(instanceId, stepDefinition.stepKey())) {
                ready.add(stepDefinition.stepKey());
            }
        }

        for (var stepKey : ready) {
            executor.submit(() -> executeReadyStep(instanceId, stepKey));
        }

        if (skippedAny) {
            scheduleAdvance(instanceId);
        }

        var refreshed = requireInstance(instanceId);
        var hasActive = refreshed.steps().stream().anyMatch(step ->
                step.status() == ProcessStepStatus.READY
                        || step.status() == ProcessStepStatus.RUNNING);
        var hasWaiting = refreshed.steps().stream().anyMatch(step ->
                step.status() == ProcessStepStatus.WAITING);

        if (!hasActive && hasWaiting
                && refreshed.status() != ProcessInstanceStatus.WAITING
                && refreshed.status() != ProcessInstanceStatus.PAUSED) {
            runtime.updateInstanceStatus(instanceId, ProcessInstanceStatus.WAITING);
        }
    }

    private void executeReadyStep(UUID instanceId, String stepKey) {
        var instance = requireInstance(instanceId);
        if (instance.status() == ProcessInstanceStatus.PAUSED || isTerminal(instance.status())) return;

        var definition = requireDefinition(instance.definitionId());
        var stepDefinition = byKey(definition.steps()).get(stepKey);
        if (stepDefinition == null) {
            failStep(instanceId, stepKey, "STEP_DEFINITION_NOT_FOUND",
                    "Step definition not found: " + stepKey);
            return;
        }

        var input = buildStepInput(instance, stepDefinition);
        try {
            contracts.validate(
                    "step.%s.input".formatted(stepKey),
                    stepDefinition.inputSchema(),
                    input);
        } catch (Exception validationError) {
            failStep(instanceId, stepKey, "INPUT_CONTRACT_VIOLATION", validationError.getMessage());
            return;
        }

        var attempt = runtime.claimReady(
                instanceId,
                stepKey,
                input,
                longValue(stepDefinition.configuration().get("timeoutSeconds")));
        if (attempt == 0) {
            return;
        }

        try {
            switch (stepDefinition.type()) {
                case SERVICE -> executeService(instanceId, stepDefinition, attempt, input);
                case AGENTIC_EXECUTION -> executeAgentic(instanceId, stepDefinition, attempt, input);
                case DECISION -> executeDecision(instanceId, stepDefinition, attempt, input);
                case HUMAN -> executeHuman(instanceId, stepDefinition, attempt, input);
                case WAIT_EVENT -> executeWaitEvent(instanceId, stepDefinition, attempt, input);
                case SUBPROCESS -> failStep(
                        instanceId,
                        stepKey,
                        "UNSUPPORTED_STEP_TYPE",
                        "SUBPROCESS execution is deferred beyond M9.4");
            }
        } catch (Exception exception) {
            handleStepFailure(
                    instanceId,
                    stepDefinition,
                    attempt,
                    "STEP_EXECUTION_ERROR",
                    exception.getMessage());
        }
    }

    private void executeService(
            UUID instanceId,
            ProcessStepDefinition step,
            int attempt,
            Map<String,Object> input) {
        var key = stringValue(step.configuration().get("serviceKey"));
        var version = integerValue(step.configuration().get("serviceVersion"));
        if (version == null) {
            throw new IllegalArgumentException(
                    "Pinned SERVICE step requires configuration.serviceVersion");
        }

        var binding = services.resolveHandler(key, version);
        contracts.validate(
                "service.%s.v%d.input".formatted(key, version),
                binding.service().inputSchema(),
                input);

        var output = binding.handler().execute(
                input,
                binding.service().configuration(),
                step.configuration());
        var safeOutput = output == null ? Map.<String,Object>of() : output;

        contracts.validate(
                "service.%s.v%d.output".formatted(key, version),
                binding.service().outputSchema(),
                safeOutput);
        completeStep(instanceId, step, attempt, safeOutput);
    }

    @SuppressWarnings("unchecked")
    private void executeAgentic(
            UUID instanceId,
            ProcessStepDefinition step,
            int attempt,
            Map<String,Object> input) {
        var instance = requireInstance(instanceId);
        var configuration = step.configuration();
        var intent = stringValue(configuration.get("intent"));
        if (intent == null || intent.isBlank()) {
            throw new IllegalArgumentException(
                    "AGENTIC_EXECUTION step requires configuration.intent");
        }

        var instructions = configuration.get("instructions") instanceof Collection<?> items
                ? items.stream().map(String::valueOf).toList()
                : List.<String>of();
        var metadata = configuration.get("metadata") instanceof Map<?,?> values
                ? new LinkedHashMap<String,Object>((Map<String,Object>) values)
                : new LinkedHashMap<String,Object>();
        metadata.put("processInstanceId", instance.id().toString());
        metadata.put("processStepKey", step.stepKey());
        metadata.put("processDefinitionKey", instance.definitionKey());
        metadata.put("processDefinitionVersion", instance.definitionVersion());

        var prepared = agentPlatform.prepare(new AgentExecutionRequest(
                stringValue(configuration.getOrDefault("name", step.stepKey())),
                intent,
                input,
                Map.of(),
                instructions,
                metadata,
                null,
                instance.correlationId(),
                step.id().toString(),
                stringValue(configuration.get("tenantId"))
        ));

        runtime.delegateAgent(instanceId, step.stepKey(), attempt, prepared.command());
    }

    private void executeDecision(
            UUID instanceId,
            ProcessStepDefinition step,
            int attempt,
            Map<String,Object> input) {
        completeStep(
                instanceId,
                step,
                attempt,
                decisions.evaluate(input, step.configuration()));
    }

    private void executeHuman(
            UUID instanceId,
            ProcessStepDefinition step,
            int attempt,
            Map<String,Object> input) {
        var config = step.configuration();
        humanTasks.createIfAbsent(new HumanTask(
                UUID.randomUUID(),
                instanceId,
                step.stepKey(),
                attempt,
                stringValue(config.getOrDefault("title", step.name())),
                stringValue(config.getOrDefault("description", step.description())),
                input,
                HumanTaskStatus.PENDING,
                null,
                Map.of(),
                Instant.now(),
                null));
        runtime.waitStep(instanceId, step.stepKey(), attempt);
    }

    private void executeWaitEvent(
            UUID instanceId,
            ProcessStepDefinition step,
            int attempt,
            Map<String,Object> input) {
        var instance = requireInstance(instanceId);
        var eventType = stringValue(step.configuration().get("eventType"));
        if (eventType == null || eventType.isBlank()) {
            throw new IllegalArgumentException("WAIT_EVENT requires configuration.eventType");
        }
        var configuredCorrelation = stringValue(step.configuration().get("correlationId"));
        var correlationId = configuredCorrelation == null || configuredCorrelation.isBlank()
                ? instance.correlationId()
                : configuredCorrelation;

        eventWaits.createIfAbsent(new ProcessEventWait(
                UUID.randomUUID(),
                instanceId,
                step.stepKey(),
                eventType,
                correlationId,
                ProcessEventWaitStatus.WAITING,
                Map.of(),
                Instant.now(),
                null));
        runtime.waitStep(instanceId, step.stepKey(), attempt);
    }

    private void handleTerminalAgentEvent(ProcessInstance instance, ExecutionEvent event) {
        if (instance.status() == ProcessInstanceStatus.CANCELLED) return;

        var step = instance.steps().stream()
                .filter(candidate -> event.execution().executionId()
                        .equals(candidate.delegatedExecutionId()))
                .findFirst()
                .orElse(null);
        if (step == null || step.status() != ProcessStepStatus.WAITING) return;

        var definition = requireDefinition(instance.definitionId());
        var stepDefinition = byKey(definition.steps()).get(step.stepKey());

        if (!event.isCompleted()) {
            var error = event.execution().error();
            handleStepFailure(
                    instance.id(),
                    stepDefinition,
                    step.attemptCount(),
                    "AGENT_EXECUTION_FAILED",
                    error == null
                            ? "Delegated Agent Platform execution ended with status "
                                + event.execution().status()
                            : String.valueOf(error.getOrDefault(
                                "message",
                                "Delegated Agent Platform execution failed")));
            return;
        }

        var result = event.execution().result() == null
                ? Map.<String,Object>of()
                : new LinkedHashMap<>(event.execution().result());
        completeStep(instance.id(), stepDefinition, step.attemptCount(), result);
    }

    private void completeWaitingStep(
            UUID instanceId,
            String stepKey,
            Map<String,Object> output) {
        var instance = requireInstance(instanceId);
        if (instance.status() == ProcessInstanceStatus.CANCELLED) return;
        var definition = requireDefinition(instance.definitionId());
        var stepDefinition = byKey(definition.steps()).get(stepKey);
        var step = instance.steps().stream()
                .filter(value -> value.stepKey().equals(stepKey))
                .findFirst()
                .orElseThrow(() -> new NoSuchElementException("Process step not found: " + stepKey));
        if (step.status() != ProcessStepStatus.WAITING) return;
        completeStep(instanceId, stepDefinition, step.attemptCount(), output);
    }

    private void completeStep(
            UUID instanceId,
            ProcessStepDefinition step,
            int expectedAttempt,
            Map<String,Object> output) {
        try {
            contracts.validate(
                    "step.%s.output".formatted(step.stepKey()),
                    step.outputSchema(),
                    output);
            if (runtime.completeStep(
                    instanceId,
                    step.stepKey(),
                    expectedAttempt,
                    output)) {
                scheduleAdvance(instanceId);
            }
        } catch (Exception validationError) {
            handleStepFailure(
                    instanceId,
                    step,
                    expectedAttempt,
                    "OUTPUT_CONTRACT_VIOLATION",
                    validationError.getMessage());
        }
    }

    private void handleStepFailure(
            UUID instanceId,
            ProcessStepDefinition step,
            int expectedAttempt,
            String code,
            String message) {
        var instance = requireInstance(instanceId);
        if (instance.status() == ProcessInstanceStatus.CANCELLED) return;

        var current = instance.steps().stream()
                .filter(value -> value.stepKey().equals(step.stepKey()))
                .findFirst()
                .orElse(null);
        if (current == null || current.attemptCount() != expectedAttempt) return;

        var retry = retryPolicy(step.configuration());
        var error = error(code, message);
        var retryableType = step.type() == ProcessStepType.SERVICE
                || step.type() == ProcessStepType.AGENTIC_EXECUTION
                || step.type() == ProcessStepType.DECISION;
        if (retryableType && current.attemptCount() < retry.maxAttempts()) {
            var multiplier = Math.max(1, current.attemptCount());
            var availableAt = Instant.now().plusMillis(retry.backoffMs() * multiplier);
            if (runtime.retryStep(
                    instanceId,
                    step.stepKey(),
                    expectedAttempt,
                    error,
                    availableAt)) {
                scheduleAdvance(instanceId);
            }
        } else {
            humanTasks.cancelPendingForInstance(instanceId);
            eventWaits.cancelWaitingForInstance(instanceId);
            runtime.failAttempt(
                    instanceId,
                    step.stepKey(),
                    expectedAttempt,
                    error);
        }
    }

    private Map<String,Object> buildStepInput(
            ProcessInstance instance,
            ProcessStepDefinition step) {
        var dependencies = new LinkedHashMap<String,Object>();
        var byKey = instance.steps().stream()
                .collect(java.util.stream.Collectors.toMap(
                        ProcessStepInstance::stepKey, value -> value));
        for (var dependencyKey : step.dependsOn()) {
            var dependency = byKey.get(dependencyKey);
            dependencies.put(
                    dependencyKey,
                    dependency == null || dependency.output() == null
                            ? Map.of()
                            : dependency.output());
        }

        var input = new LinkedHashMap<String,Object>();
        input.put("processInput", instance.input());
        input.put("context", instance.context());
        input.put("dependencies", dependencies);
        return input;
    }

    @SuppressWarnings("unchecked")
    private boolean conditionMatches(
            Map<String,Object> context,
            Map<String,Object> configuration) {
        var when = configuration.get("when");
        if (!(when instanceof Map<?,?> values)) return true;
        return decisions.conditionMatches(
                context,
                new LinkedHashMap<>((Map<String,Object>) values));
    }

    private ReviewPolicy reviewPolicy(Map<String,Object> configuration) {
        var value = configuration.get("review");
        if (!(value instanceof Map<?,?> review)) return null;

        var repeatStep = stringValue(review.get("repeatStep"));
        var repeatDecision = stringValue(
                review.containsKey("repeatDecision")
                        ? review.get("repeatDecision")
                        : "REQUEST_CHANGES");
        var approveDecision = stringValue(
                review.containsKey("approveDecision")
                        ? review.get("approveDecision")
                        : "APPROVE");
        var maxIterations = integerValue(
                review.containsKey("maxIterations")
                        ? review.get("maxIterations")
                        : 5);

        return new ReviewPolicy(
                repeatStep,
                approveDecision,
                repeatDecision,
                Math.max(1, maxIterations == null ? 5 : maxIterations));
    }

    private RetryPolicy retryPolicy(Map<String,Object> configuration) {
        var value = configuration.get("retry");
        if (!(value instanceof Map<?,?> map)) return new RetryPolicy(1, 0);
        var maxAttempts = integerValue(map.get("maxAttempts"));
        var backoffMs = longValue(map.get("backoffMs"));
        return new RetryPolicy(
                Math.max(1, maxAttempts == null ? 1 : maxAttempts),
                Math.max(0, backoffMs == null ? 0 : backoffMs));
    }

    private void failStep(UUID instanceId, String stepKey, String code, String message) {
        humanTasks.cancelPendingForInstance(instanceId);
        eventWaits.cancelWaitingForInstance(instanceId);
        runtime.failStep(instanceId, stepKey, error(code, message));
    }

    private static Map<String,Object> error(String code,String message) {
        var error = new LinkedHashMap<String,Object>();
        error.put("code", code);
        error.put("message", message == null ? code : message);
        return error;
    }

    private ProcessInstance requireInstance(UUID id) {
        return runtime.findInstance(id)
                .orElseThrow(() -> new NoSuchElementException(
                        "Process instance not found: " + id));
    }

    private ProcessDefinition requireDefinition(UUID id) {
        return definitions.findById(id)
                .orElseThrow(() -> new NoSuchElementException(
                        "Process definition not found: " + id));
    }

    private static Map<String,ProcessStepDefinition> byKey(List<ProcessStepDefinition> steps) {
        return steps.stream().collect(
                java.util.stream.Collectors.toMap(
                        ProcessStepDefinition::stepKey,
                        step -> step,
                        (left, right) -> left,
                        LinkedHashMap::new));
    }

    private static boolean isTerminal(ProcessInstanceStatus status) {
        return status == ProcessInstanceStatus.COMPLETED
                || status == ProcessInstanceStatus.FAILED
                || status == ProcessInstanceStatus.CANCELLED;
    }

    private static String stringValue(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private static Integer integerValue(Object value) {
        if (value == null) return null;
        if (value instanceof Number number) return number.intValue();
        return Integer.valueOf(String.valueOf(value));
    }

    private static Long longValue(Object value) {
        if (value == null) return null;
        if (value instanceof Number number) return number.longValue();
        return Long.valueOf(String.valueOf(value));
    }

    private static Map<String,Object> safeMap(Map<String,Object> value) {
        return value == null ? Map.of() : new LinkedHashMap<>(value);
    }

    private void scheduleAdvance(UUID instanceId) {
        if (TransactionSynchronizationManager.isActualTransactionActive()
                && TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(
                    new TransactionSynchronization() {
                        @Override
                        public void afterCommit() {
                            submitAdvance(instanceId);
                        }
                    });
            return;
        }
        submitAdvance(instanceId);
    }

    private void submitAdvance(UUID instanceId) {
        executor.submit(() -> {
            try {
                advance(instanceId);
            } catch (Exception ignored) {
                // Durable state remains authoritative; recovery will retry progression.
            }
        });
    }

    @PreDestroy
    void shutdown() {
        executor.shutdownNow();
    }

    private record RetryPolicy(int maxAttempts,long backoffMs) {}
    private record ReviewPolicy(
            String repeatStep,
            String approveDecision,
            String repeatDecision,
            int maxIterations) {}
}
