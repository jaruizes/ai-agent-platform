package com.jaruizes.processplatform.infrastructure.api.rest;

import com.jaruizes.processplatform.business.ProcessRuntimeService;
import com.jaruizes.processplatform.domain.model.ProcessInstance;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/v1/process-instances")
public class ProcessRuntimeController {

    private final ProcessRuntimeService runtime;

    public ProcessRuntimeController(ProcessRuntimeService runtime) {
        this.runtime = runtime;
    }

    @PostMapping("/{id}/start")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public ProcessInstance start(@PathVariable UUID id) {
        return runtime.start(id);
    }
}
