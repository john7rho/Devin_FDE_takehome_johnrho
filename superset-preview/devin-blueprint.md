# Per-project Superset on Devin (Blueprint + shareable preview)

Goal: every Devin session on the Superset project boots with Apache Superset +
example data already built, so a session can expose it publicly (a
`*.devinapps.com` URL) within seconds instead of building from scratch.

> Reality check: Devin VMs are **per-session and ephemeral**. A Blueprint bakes
> Superset into the snapshot so each session starts ready, but the shared URL
> lives only while that session (and keep-alive) is up. For a *permanently*
> hosted, always-on Superset, use a real container host instead.

## 1. Create the Blueprint (one-time, in the Devin dashboard)

Devin dashboard → Environment → Blueprints (or the blueprint API). Put these in
the **build / initialize** step so the result is baked into the snapshot:

```bash
docker pull apache/superset:4.1.1
docker run -d -p 8088:8088 --name superset apache/superset:4.1.1
docker exec superset superset db upgrade
docker exec superset superset fab create-admin \
  --username admin --password admin --firstname a --lastname b --email a@b.com || true
docker exec superset superset load_examples
docker exec superset superset init
```

Build it once (~5–15 min). Docs: https://docs.devin.ai/onboard-devin/environment/blueprints

## 2. Pin the snapshot for the preview endpoint

After the build, grab the snapshot id and set it on the backend so
`POST /api/v1/superset-preview` launches sessions from it:

```bash
DEVIN_SUPERSET_SNAPSHOT_ID=<snapshot-id>
```

## 3. Use it

The dashboard's **Preview Superset** button calls `POST /api/v1/superset-preview`
→ Devin session boots Superset (from the snapshot) and runs `expose_port 8088` →
the backend polls for the public `devinapps.com` URL → the dashboard shows an
**Open Superset** link. No Devin account needed for the reviewer who clicks it.
