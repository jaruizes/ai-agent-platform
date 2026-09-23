package com.jaruizes.processplatform.domain.ports;

import com.jaruizes.processplatform.domain.model.ExecutionCommand;

public interface AgentPlatformCommandPort {
    void submit(ExecutionCommand command);
}
