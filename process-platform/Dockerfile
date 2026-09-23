FROM maven:3.9.11-eclipse-temurin-21 AS build
WORKDIR /workspace
COPY process-platform/pom.xml .
RUN mvn -q -DskipTests dependency:go-offline
COPY process-platform/src ./src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /workspace/target/process-platform-*.jar app.jar
EXPOSE 8090
ENTRYPOINT ["java","-jar","/app/app.jar"]
