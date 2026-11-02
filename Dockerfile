FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

FROM builder AS aws-wheels
RUN pip wheel --no-cache-dir --wheel-dir /wheels-aws ".[aws]"

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --system appuser && useradd --system --gid appuser --uid 999 appuser
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels template-api-python && rm -rf /wheels
COPY alembic.ini ./
COPY alembic ./alembic
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8080/health/ready', timeout=2)"
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]

# AWS Lambda image: build with --target lambda. Adds boto3 (the `aws` extra) so the app can read its
# database credentials from Secrets Manager. The Lambda Web Adapter forwards invocations to the
# server above and waits for the readiness path before accepting traffic.
FROM runtime AS lambda
USER root
RUN --mount=type=bind,from=aws-wheels,source=/wheels-aws,target=/wheels-aws \
    pip install --no-cache-dir --no-index --find-links=/wheels-aws "template-api-python[aws]"
USER appuser
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter
ENV AWS_LWA_PORT=8080 AWS_LWA_READINESS_CHECK_PATH=/health/ready

# The last stage is the default target (ECS and local use), so it must stay free of the adapter.
# BuildKit skips the unused stages; the legacy builder would build the lambda stage too.
FROM runtime
