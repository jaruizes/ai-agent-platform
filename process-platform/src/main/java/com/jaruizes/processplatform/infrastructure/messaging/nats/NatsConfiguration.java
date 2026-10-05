package com.jaruizes.processplatform.infrastructure.messaging.nats;

import io.nats.client.Connection;
import io.nats.client.Nats;
import io.nats.client.Options;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.io.IOException;
import java.time.Duration;

@Configuration
@EnableConfigurationProperties(AgentPlatformNatsProperties.class)
public class NatsConfiguration {

    @Bean(destroyMethod = "close")
    Connection natsConnection(AgentPlatformNatsProperties properties)
            throws IOException, InterruptedException {
        var options = new Options.Builder()
                .server(properties.url())
                .connectionName("process-platform")
                .maxReconnects(-1)
                .reconnectWait(Duration.ofSeconds(2))
                .build();
        return Nats.connect(options);
    }
}
