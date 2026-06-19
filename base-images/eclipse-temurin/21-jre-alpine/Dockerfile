# Golden hardened base — eclipse-temurin:21-jre-alpine with OS packages patched.
# Final-stage base for the fleet's Java (JRE) runtimes. See the 17-jre-alpine
# sibling and base-images/node/22-alpine/Dockerfile for the full rationale.
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jre-alpine@sha256:704db3c40204a44f471191446ddd9cda5d60dab40f0e15c6507b815ed897238b

RUN apk upgrade --no-cache
