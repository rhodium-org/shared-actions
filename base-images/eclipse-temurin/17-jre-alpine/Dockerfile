# Golden hardened base — eclipse-temurin:17-jre-alpine with OS packages patched.
# Final-stage base for the fleet's Java (JRE) runtimes. Alpine-based, so it
# carries the same OS-layer openssl/libcrypto3 CVEs. See
# base-images/node/22-alpine/Dockerfile for the full rationale. (Application
# JAR/library CVEs are the consumer's concern and are caught by the app's own
# os,library gate.) Rebuilt daily; published PUBLIC for anonymous PR pulls.
FROM public.ecr.aws/docker/library/eclipse-temurin:17-jre-alpine@sha256:b0ae54a36f82e04dc6c45e40ca5c55762e20b9a0858ee457faf557d440a9b571

RUN apk upgrade --no-cache
