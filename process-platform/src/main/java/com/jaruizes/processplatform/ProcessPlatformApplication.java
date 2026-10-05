package com.jaruizes.processplatform;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class ProcessPlatformApplication {

    public static void main(String[] args) {
        SpringApplication.run(ProcessPlatformApplication.class, args);
    }
}
