package org.ossustain;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

import static org.assertj.core.api.Assertions.assertThat;

@Testcontainers
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class HealthEndpointIntegrationTest {
    @Container
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:16.15")
            .withDatabaseName("ossustain")
            .withUsername("ossustain")
            .withPassword("test-password");

    @DynamicPropertySource
    static void configureDatabase(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", POSTGRES::getUsername);
        registry.add("spring.datasource.password", POSTGRES::getPassword);
    }

    @LocalServerPort
    private int port;

    @Test
    void healthEndpointIsUpAndFlywayAppliedTheBaseline() throws Exception {
        var request = HttpRequest.newBuilder(URI.create("http://localhost:" + port
                + "/actuator/health")).GET().build();
        var response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());

        assertThat(response.statusCode()).isEqualTo(HttpStatus.OK.value());
        assertThat(response.body()).contains("\"status\":\"UP\"");
        assertThat(POSTGRES.execInContainer("psql", "-U", "ossustain", "-d", "ossustain", "-Atc",
                "SELECT version FROM flyway_schema_history WHERE version = '1'").getStdout().trim())
                .isEqualTo("1");
    }

    @Test
    void flywayCreatesTheCohortSelectionSchema() throws Exception {
        var result = POSTGRES.execInContainer("psql", "-U", "ossustain", "-d", "ossustain", "-Atc",
                "SELECT version FROM flyway_schema_history WHERE version = '2'");

        assertThat(result.getStdout().trim()).isEqualTo("2");
        assertThat(POSTGRES.execInContainer("psql", "-U", "ossustain", "-d", "ossustain", "-Atc",
                "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' "
                        + "AND table_name IN ('repositories', 'cohorts', 'cohort_memberships')")
                .getStdout().trim()).isEqualTo("3");
    }
}
