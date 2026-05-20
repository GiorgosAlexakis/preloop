# Railway Trial Deployment

This directory defines the self-contained Railway trial path for Preloop OSS.
It is meant for evaluation: a public URL, private service wiring, generated
secrets, and persistent Postgres storage. It is not a hardened production guide.

## Topology

The trial uses four Railway services plus one volume:

| Service | Source | Public | Purpose |
|---|---|---:|---|
| `console` | `ghcr.io/preloop/console:<version>` | Yes | Single public URL. Proxies UI, API, MCP, and gateway paths. |
| `api-gateway` | `ghcr.io/preloop/preloop:<version>` | No | Runs API and model gateway in `PRELOOP_SERVICE_ROLE=all` trial mode. |
| `worker-scheduler` | `ghcr.io/preloop/preloop:<version>` | No | Runs `preloop-sync scheduler` and `preloop-sync worker` together for trial deployments. |
| `postgres` | `pgvector/pgvector:pg16` | No | Self-contained database with pgvector and a persistent volume. |
| `nats` | `nats:alpine` | No | Private JetStream event bus for flow and UI events. |

The published Railway template should mirror `template-services.yaml`. The
Compose file is a staging scaffold for Railway's Compose import flow and for
local review of the service map.

## Public and Private URLs

Only `console` should have public HTTP networking enabled.

- Public Preloop URL: `https://${{console.RAILWAY_PUBLIC_DOMAIN}}`
- Console to API: `http://${{api-gateway.RAILWAY_PRIVATE_DOMAIN}}:8000`
- Console to gateway: `http://${{api-gateway.RAILWAY_PRIVATE_DOMAIN}}:8000`
- API to Postgres: `${{postgres.RAILWAY_PRIVATE_DOMAIN}}:5432`
- API and worker to NATS: `${{nats.RAILWAY_PRIVATE_DOMAIN}}:4222`

The console nginx image proxies:

- `/api`, `/mcp`, `/oauth`, `/.well-known`, `/approval`, and `/install` to
  `API_URL`
- `/openai`, `/anthropic`, and `/gemini` to `GATEWAY_URL`

Because API and gateway share the same private service in trial mode, both
`API_URL` and `GATEWAY_URL` point to `api-gateway`.

## Template Variables

Configure these as shared Railway template variables:

| Variable | Value |
|---|---|
| `PRELOOP_VERSION` | `latest` for the public trial, or a released tag. |
| `LOG_LEVEL` | `INFO` |
| `SECRET_KEY` | `${{secret(64, "abcdef0123456789")}}` |
| `POSTGRES_PASSWORD` | `${{secret(32)}}` |

The service-specific variables are listed in `template-services.yaml`. Keep the
published template and that file in sync.

## Service Settings

Use these settings when creating or updating the Railway template:

1. Create `postgres` from `pgvector/pgvector:pg16`, attach a volume at
   `/var/lib/postgresql/data`, and keep public networking disabled.
2. Create `nats` from `nats:alpine`, use start command
   `nats-server -js -m 8222`, and keep public networking disabled.
3. Create `api-gateway` from `ghcr.io/preloop/preloop:${{shared.PRELOOP_VERSION}}`,
   use start command `sh scripts/start_trial_api.sh`, set health check path
   `/api/v1/health`, and keep public networking disabled.
4. Create `worker-scheduler` from
   `ghcr.io/preloop/preloop:${{shared.PRELOOP_VERSION}}`, use start command
   `sh scripts/run_trial_worker_scheduler.sh`, and keep public networking
   disabled.
5. Create `console` from `ghcr.io/preloop/console:${{shared.PRELOOP_VERSION}}`,
   enable public HTTP networking, and set health check path `/health`.

## Smoke Test

After deploying the template:

1. Open the public console URL and confirm the app loads.
2. Visit `/api/v1/health` through the public console URL and confirm the backend
   returns healthy JSON.
3. Create the first user or sign in.
4. Run `preloop agents discover --preloop-url <public-console-url>` from a local
   machine and enroll a test agent.
5. Send one model call through `/openai/v1` and confirm the gateway event appears
   in the UI.
6. Trigger one MCP policy event and confirm it appears in the audit timeline.

## Teardown and Persistence

To stop paying for a trial, delete the Railway project from the Railway project
settings. Removing only the public `console` service leaves the private services
and the Postgres volume running.

The `postgres` volume persists user accounts, API keys, tracker config, policies,
audit logs, runtime sessions, flow executions, and gateway usage. Deleting the
project or deleting the `postgres-data` volume removes that data.

NATS keeps JetStream state only for the life of the service unless a separate
NATS volume is attached. The default trial template does not attach one; durable
application state lives in Postgres.
