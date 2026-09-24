package com.jaruizes.processplatform.infrastructure.api.rest;

import com.jaruizes.processplatform.business.ProcessRuntimeService;
import com.jaruizes.processplatform.domain.model.HumanTask;
import com.jaruizes.processplatform.infrastructure.api.rest.dto.CompleteHumanTaskRequest;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/v1/human-tasks")
public class HumanTaskController {
    private final ProcessRuntimeService runtime;
    public HumanTaskController(ProcessRuntimeService runtime){this.runtime=runtime;}

    @GetMapping
    public List<HumanTask> list(
            @RequestParam(name="pendingOnly", defaultValue="false") boolean pendingOnly) {
        return runtime.humanTasks(pendingOnly);
    }

    @PostMapping("/{id}/complete")
    public HumanTask complete(
            @PathVariable UUID id,
            @Valid @RequestBody CompleteHumanTaskRequest request) {
        return runtime.completeHumanTask(id, request.decision(), request.result());
    }
}
