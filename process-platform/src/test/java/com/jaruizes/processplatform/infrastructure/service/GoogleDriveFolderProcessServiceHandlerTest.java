package com.jaruizes.processplatform.infrastructure.service;

import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;

import java.util.Map;

import static org.assertj.core.api.Assertions.*;

class GoogleDriveFolderProcessServiceHandlerTest {

    private final GoogleDriveFolderProcessServiceHandler handler =
            new GoogleDriveFolderProcessServiceHandler(RestClient.builder());

    @Test
    void acceptsDefaultTokenAndFolderPathConfiguration() {
        assertThatCode(() -> handler.validateConfiguration(Map.of()))
                .doesNotThrowAnyException();
    }

    @Test
    void rejectsBlankTokenEnvironmentName() {
        assertThatThrownBy(() -> handler.validateConfiguration(
                Map.of("accessTokenEnv", "")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("accessTokenEnv");
    }

    @Test
    void rejectsBlankFolderPath() {
        assertThatThrownBy(() -> handler.validateConfiguration(
                Map.of("folderIdPath", "")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("folderIdPath");
    }
}
