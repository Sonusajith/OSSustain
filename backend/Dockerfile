FROM maven:3.9.11-eclipse-temurin-21 AS build

WORKDIR /workspace
COPY backend/pom.xml backend/pom.xml
COPY backend/src backend/src
RUN mvn -B -ntp -f backend/pom.xml -Dmaven.test.skip=true package

FROM eclipse-temurin:21-jre-alpine

RUN apk upgrade --no-cache \
    && apk add --no-cache curl

WORKDIR /app
COPY --from=build --chown=10001:10001 \
    /workspace/backend/target/ossustain-api-0.1.0-SNAPSHOT.jar /app/ossustain-api.jar

USER 10001:10001
EXPOSE 8080
ENV JAVA_TOOL_OPTIONS="-Duser.timezone=UTC -XX:MaxRAMPercentage=70.0"
HEALTHCHECK --interval=20s --timeout=3s --start-period=45s --retries=5 \
    CMD curl --fail --silent http://127.0.0.1:8080/actuator/health || exit 1
ENTRYPOINT ["java", "-jar", "/app/ossustain-api.jar"]
