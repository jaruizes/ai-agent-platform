package com.jaruizes.processplatform.infrastructure.google;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.*;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class GoogleOAuthAccessTokenProviderTest {

    @TempDir
    Path tempDir;

    @Test
    void refreshesAccessTokenFromStoredAuthorizedUserAndCachesIt() throws Exception {
        var tokenFile = tempDir.resolve("google-token.json");
        Files.writeString(tokenFile, """
                {
                  "type": "authorized_user",
                  "client_id": "client-id",
                  "client_secret": "client-secret",
                  "refresh_token": "refresh-token"
                }
                """);

        var builder = RestClient.builder();
        var server = MockRestServiceServer.bindTo(builder).build();
        server.expect(once(), requestTo("https://oauth.test/token"))
                .andExpect(content().contentType(MediaType.APPLICATION_FORM_URLENCODED))
                .andExpect(content().string(org.hamcrest.Matchers.allOf(
                        org.hamcrest.Matchers.containsString("client_id=client-id"),
                        org.hamcrest.Matchers.containsString("client_secret=client-secret"),
                        org.hamcrest.Matchers.containsString("refresh_token=refresh-token"),
                        org.hamcrest.Matchers.containsString("grant_type=refresh_token"))))
                .andRespond(withSuccess(
                        "{\"access_token\":\"access-123\",\"expires_in\":3600,\"token_type\":\"Bearer\"}",
                        MediaType.APPLICATION_JSON));

        var provider = new GoogleOAuthAccessTokenProvider(
                builder,
                new ObjectMapper(),
                tokenFile.toString(),
                "https://oauth.test/token");

        assertThat(provider.accessToken()).isEqualTo("access-123");
        assertThat(provider.accessToken()).isEqualTo("access-123");
        server.verify();
    }

    @Test
    void failsClearlyWhenStoredTokenIsMissing() {
        var provider = new GoogleOAuthAccessTokenProvider(
                RestClient.builder(),
                new ObjectMapper(),
                tempDir.resolve("missing.json").toString(),
                "https://oauth.test/token");

        assertThatThrownBy(provider::accessToken)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Google OAuth token file not found");
    }

    @Test
    void failsClearlyWhenRefreshTokenIsMissing() throws Exception {
        var tokenFile = tempDir.resolve("google-token.json");
        Files.writeString(tokenFile, """
                {
                  "type": "authorized_user",
                  "client_id": "client-id",
                  "client_secret": "client-secret"
                }
                """);

        var provider = new GoogleOAuthAccessTokenProvider(
                RestClient.builder(),
                new ObjectMapper(),
                tokenFile.toString(),
                "https://oauth.test/token");

        assertThatThrownBy(provider::accessToken)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("refresh_token");
    }
}
