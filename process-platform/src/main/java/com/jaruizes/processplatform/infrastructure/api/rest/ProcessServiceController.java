package com.jaruizes.processplatform.infrastructure.api.rest;

import com.jaruizes.processplatform.business.ProcessServiceCatalogService;
import com.jaruizes.processplatform.domain.model.ProcessServiceDefinition;
import com.jaruizes.processplatform.infrastructure.api.rest.dto.CreateProcessServiceRequest;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/v1/process-services")
public class ProcessServiceController {
    private final ProcessServiceCatalogService services;
    public ProcessServiceController(ProcessServiceCatalogService services){this.services=services;}

    @GetMapping public List<ProcessServiceDefinition> list(){return services.list();}
    @GetMapping("/{id}") public ProcessServiceDefinition get(@PathVariable UUID id){return services.get(id);}

    @PostMapping @ResponseStatus(HttpStatus.CREATED)
    public ProcessServiceDefinition create(@Valid @RequestBody CreateProcessServiceRequest r){
        return services.create(r.serviceKey(),r.name(),r.description(),r.version(),r.implementationKey(),r.inputSchema(),r.outputSchema());
    }

    @PostMapping("/{id}/activate")
    public ProcessServiceDefinition activate(@PathVariable UUID id){return services.activate(id);}

    @PostMapping("/{id}/retire")
    public ProcessServiceDefinition retire(@PathVariable UUID id){return services.retire(id);}
}
