# Python API template

A minimal Python 3.12+ FastAPI application with Pydantic v2, Clean Architecture, environment YAML configuration, SQLAlchemy async PostgreSQL support, Alembic, and Docker.

The public API contains health endpoints only. A test-only Item example demonstrates DDD entities, application use cases, repository ports, and interchangeable memory/PostgreSQL adapters without adding business tables to the application.

## Local startup

Use the shared Python environment when available:

```sh
source /Users/alonso/Documents/Workspace/pipenvdev/dev/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:create_app --factory --reload --port 8080
```

The default local profile uses memory and needs no database. If the shared environment is incompatible, activate an existing project virtual environment; do not install into system Python.

| Endpoint | Success | Failure |
|---|---|---|
| `GET /health` | 200, `{"status":"ok"}` | Process availability only |
| `GET /health/ready` | 200, `{"status":"ready"}` | 503, `{"status":"not_ready"}` |

PostgreSQL readiness runs `SELECT 1` with a two-second timeout. Liveness remains available during database outages. Swagger, ReDoc, and OpenAPI are enabled only in the local and container profiles.

## Configuration

The module in `src/app/config` follows the OpenProjectsHub configuration workflow, with typed, immutable settings instead of a global singleton.

| `APP_ENV` | Default backend | PostgreSQL host default |
|---|---|---|
| `local` | memory | localhost |
| `test` | memory | localhost |
| `dev` | postgresql | localhost |
| `container` | postgresql | postgres |
| `prod` | postgresql | Required |

`APP_ENV` defaults to `local`. Profiles are selected at startup from packaged `config_<profile>.yml` files. Restart the process after changing configuration.

An optional `.env` is read from the working directory. Process environment variables take precedence. Production ignores `.env` values, including when `.env` selects the production profile. Loading configuration never changes `os.environ`.

Tagged YAML scalars support `!ENV ${VARIABLE}` and `!ENV ${VARIABLE:default}`, including interpolation within a string. Missing required variables, malformed YAML, unknown profiles, and invalid fields fail startup with messages that omit configuration values. Arbitrary nested environment overrides are not supported; expose each override explicitly in YAML.

Set `PERSISTENCE_DRIVER=postgresql` to use PostgreSQL. Supply `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`. The password has no usable default. Production also requires explicit host, user, and database values. For memory mode, database credentials are not required. Set `APP_NAME` and `LOG_LEVEL` to override application metadata and logging.

Optional settings for managed databases and browsers (defaults keep the previous behavior):

| Variable | Values | Use |
|---|---|---|
| `POSTGRES_SSL_MODE` | `disable` (default), `require` | `require` encrypts the connection for RDS and Supabase without verifying the server certificate (verification is TBD). `disable` sends no SSL setting, so asyncpg's default (`prefer`) still negotiates TLS when the server offers it. |
| `POSTGRES_POOL_MODE` | `queue` (default), `null` | `null` disables SQLAlchemy pooling and asyncpg prepared-statement reuse. Use it behind a transaction-mode pooler (Supabase pooler, PgBouncer) and on AWS Lambda. |
| `POSTGRES_CREDENTIALS_JSON` | `{"username":"...","password":"..."}` | Sets the user and password from one JSON value, the format of an RDS-managed secret. ECS injects it from Secrets Manager. Overrides `POSTGRES_USER` and `POSTGRES_PASSWORD`; available in the `dev`, `container`, and `prod` profiles. |
| `POSTGRES_CREDENTIALS_SECRET_ARN` | Secrets Manager secret ARN | Reads the credentials JSON above from AWS at startup, so no password is stored in the environment. Needs the `aws` extra (`pip install '.[aws]'`) and `secretsmanager:GetSecretValue` on the secret. Ignored when `POSTGRES_CREDENTIALS_JSON` is set. Failures stop startup and report only the error type. The secret is read once at startup, so after a rotation restart the service. Ignored outside the `dev`, `container`, and `prod` profiles or with `PERSISTENCE_DRIVER=memory`. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins | Empty disables CORS. Origins must look like `https://host[:port]` with no path or trailing slash; `*` is rejected. Only the `Authorization` and `Content-Type` headers are allowed and credentials are not. |

Never commit `.env` or print settings with unredacted secrets. `.env.example` contains variable names and no usable credentials.

## Docker

For PostgreSQL, copy `.env.example` to `.env` and set your own `POSTGRES_PASSWORD`:

```sh
docker compose up --build --wait
```

Compose selects the container/PostgreSQL profile, waits for PostgreSQL, runs Alembic once, and then starts the API on port 8080. `APP_PORT` changes the host port. PostgreSQL data uses a named volume, and the database port is not exposed to the host.

For a standalone memory container:

```sh
docker build -t template-api-python:local .
docker run --rm -p 8080:8080 -e APP_ENV=container -e PERSISTENCE_DRIVER=memory template-api-python:local
```

The image runs as non-root UID 999. Configuration YAML is packaged with the application; host `.env`, virtual environments, and test fixtures are excluded from the image. Image tags and dependency bounds are a starter baseline; release builds should lock their resolved dependencies and image digest.

## Deployment targets

| Target | Build | Notes |
|---|---|---|
| Container (ECS, local) | `docker build .` | Default image. Use `/health` for load balancer checks and `/health/ready` for container checks. |
| AWS Lambda | `docker build --target lambda .` | Adds the [AWS Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter) extension with port 8080 and `/health/ready` as the readiness path. Push to a private ECR repository (the shared `docker-push` workflow accepts `target: lambda`) and deploy by digest. Set `POSTGRES_POOL_MODE=null` and `POSTGRES_CREDENTIALS_SECRET_ARN`. |

Building the `lambda` target pulls the adapter layer from `public.ecr.aws`. The adapter runs only inside Lambda, so a local `docker run` of that image tests the application, not the adapter.

Run migrations as a separate, one-off step with the same image (`alembic upgrade head`), never at startup. Behind a transaction-mode pooler, point migrations at the direct database connection or the session pooler.

## Migrations

Alembic reads the same validated settings as the API. For local CLI use, select PostgreSQL and set connection variables in `.env` or the process environment:

```sh
alembic upgrade head
alembic revision --autogenerate -m "add feature tables"
alembic check
```

The initial baseline establishes Alembic history without creating business tables. Model registration belongs in the shared infrastructure metadata registry. Import each new feature's ORM models there before generating a migration, inspect the generated revision, and run it explicitly before deploying the API. The application never runs migrations or `create_all()` at startup.

Production Alembic configuration never discovers the Item test migrations. The repository's Alembic files are deployment assets; run CLI migrations from the checkout or supplied Docker image, not from a wheel alone.

## Architecture and adding a feature

```text
src/app/
  config/                   # YAML loading and validated settings
  container.py              # Concrete dependency assembly
  main.py                   # Application factory and router registration
  features/<feature>/
    domain/                 # Pure entities, invariants, repository ports
    application/            # Use cases and boundary contracts
    infrastructure/         # ORM models and concrete adapters
    presentation/           # FastAPI routers and Pydantic HTTP schemas
  shared/infrastructure/    # Database URL, engine, and model registry
tests/
  unit/
  integration/
  architecture/
  support/items/            # Test-only entity, use cases, and adapters
  fixtures/alembic/          # Test-only migration extension
```

Only create layers that the feature needs. Health has no domain layer because it has no business invariants.

1. Define domain entities and invariants with standard Python types.
2. Define an intention-revealing repository port and application use cases. Return application result objects across the presentation boundary.
3. Implement infrastructure adapters and map explicitly between ORM records and domain entities.
4. Keep routes thin and define Pydantic request/response schemas in presentation.
5. Assemble concrete dependencies in `container.py`, register the router in `main.py`, and add focused tests.
6. Register ORM metadata and add an inspected Alembic migration if persistence is needed.

Domain and application layers cannot import framework or infrastructure code. Presentation may use the composition root for dependency providers. Health backend selection is independent of the test-only repositories.

The application container owns one engine/session factory per lifespan. Give each operation its own session. Repository writes flush; the application operation or its composition boundary commits or rolls back the transaction before returning a response:

```python
async with session_factory() as session, session.begin():
    result = await CreateItem(PostgreSQLItemRepository(session)).execute(command)
```

The snippet illustrates the test-only example. No generic repository, unit-of-work framework, authentication, or domain event infrastructure is included.

## Verification

Run fast checks without a database:

```sh
python -m pytest -m "not postgres"
ruff check .
ruff format --check .
mypy
python -m build
```

Run real PostgreSQL repository and migration tests:

```sh
python scripts/test_postgres.py
```

The runner requires a local Docker socket and rejects remote Docker hosts/contexts before starting containers. It creates a uniquely named Compose project, generates an ephemeral password, discovers a loopback-only port, runs the PostgreSQL-marked tests, and removes its containers afterward. The test database uses temporary storage, never the application volume. Test connection settings are derived only from the runner, never from application configuration or an arbitrary DSN. Tests reject non-test environments and database identities.

PostgreSQL tests cover repository parity, commit/rollback, readiness, and migration upgrade/downgrade/re-upgrade/schema drift. An unfiltered `pytest` requires the PostgreSQL runner environment; use the commands above for the two suites.

Architecture tests enforce inward imports for production features and the test-only example. The application wheel includes config YAML and excludes test packages. The package build uses a disposable PEP 517 environment with compatible setuptools, leaving shared tooling unchanged. If using `--no-isolation`, the active environment requires setuptools 68 or newer for Python 3.12 compatibility.
