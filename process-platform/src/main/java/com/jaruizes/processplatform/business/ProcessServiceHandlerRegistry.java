package com.jaruizes.processplatform.business;

import com.jaruizes.processplatform.domain.ports.ProcessServiceHandlerPort;
import org.springframework.stereotype.Component;

import java.util.*;

@Component
public class ProcessServiceHandlerRegistry {

    private final Map<String,ProcessServiceHandlerPort> handlers;

    public ProcessServiceHandlerRegistry(List<ProcessServiceHandlerPort> handlers) {
        var map = new LinkedHashMap<String,ProcessServiceHandlerPort>();
        for (var handler : handlers) {
            if (map.put(handler.key(), handler) != null) {
                throw new IllegalStateException(
                        "Duplicate process service handler: " + handler.key());
            }
        }
        this.handlers = Map.copyOf(map);
    }

    public ProcessServiceHandlerPort require(String key) {
        if (key == null || key.isBlank()) {
            throw new IllegalArgumentException(
                    "Process service implementation key is required");
        }
        var handler = handlers.get(key);
        if (handler == null) {
            throw new IllegalArgumentException(
                    "No ProcessServiceHandler registered for key: " + key);
        }
        return handler;
    }
}
