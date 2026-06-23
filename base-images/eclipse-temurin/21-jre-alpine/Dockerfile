# Golden hardened base — eclipse-temurin:21-jre-alpine with OS packages patched.
# Final-stage base for the fleet's Java (JRE) runtimes. See the 17-jre-alpine
# sibling and base-images/node/22-alpine/Dockerfile for the full rationale.
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jre-alpine@sha256:3f08b13888f595cc49edabea7250ba69499ba25602b267da591720769400e08c

RUN apk upgrade --no-cache
