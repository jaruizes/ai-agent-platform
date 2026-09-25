package com.jaruizes.processplatform.infrastructure.service;

import com.jaruizes.processplatform.infrastructure.google.GoogleOAuthAccessTokenProvider;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;

import java.util.Map;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.mock;

class GoogleDriveFolderProcessServiceHandlerTest {

    private final GoogleDriveFolderProcessServiceHandler handler =
            new GoogleDriveFolderProcessServiceHandler(
                    RestClient.builder(),
                    mock(GoogleOAuthAccessTokenProvider.class));

    @Test
    void acceptsDefaultFolderPathConfiguration() {
        assertThatCode(() -> handler.validateConfiguration(Map.of()))
                .doesNotThrowAnyException();
    }

    @Test
    void ignoresLegacyAccessTokenEnvironmentConfiguration() {
        assertThatCode(() -> handler.validateConfiguration(
                Map.of("accessTokenEnv", "")))
                .doesNotThrowAnyException();
    }

    @Test
    void rejectsBlankFolderPath() {
        assertThatThrownBy(() -> handler.validateConfiguration(
                Map.of("folderIdPath", "")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("folderIdPath");
    }
}
