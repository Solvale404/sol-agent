# Sol Agent

> [Architecture](docs/architecture.md) · [Development](docs/development.md) · [Verified status](docs/project-status.md) · [Releases](https://github.com/Solvale404/sol-agent/releases)

**Responsibility:** Sol's self-contained resident iPhone agent and direct Home Assistant control path.

**Interface:** Resident iPhone service and local HA interface; no public hosted dashboard.


Resident control plane for **Sol** — a jailbroken iPhone that should keep useful local/home capabilities working without a Mac in the loop.

> Status: **staging / parallel migration**. This repository must not replace the current working Sol stack until the migration gates in `MIGRATION.md` pass.

## Design goals

- **Mac-independent normal runtime**
- **Home Assistant ↔ Sol directly** over the LAN
- **Local-first**: core control still works if the internet is down
- **Bounded capabilities**: named actions only; no generic remote shell
- **Acknowledged commands** with idempotency, expiry and auditability
- **Direct rescue path** that does not require Home Assistant
- **Preserve direct messaging** and existing resident services while migration is underway
- **Human foreground control always wins**

## Architecture

```text
Home Assistant / MQTT
        │
        ▼
  sol-agent daemon  ◄──── SSH + solctl (rescue)
        │
        ├── allow-listed action dispatcher
        │      ├── RemoteCompanion `rc` (preferred low-level actuator)
        │      ├── existing Sol local bridge (optional high-level adapter)
        │      └── iOS-MCP (optional UI adapter where still justified)
        │
        ├── retained health + capability manifest
        ├── command acknowledgement + dedupe database
        └── local audit log
```

RemoteCompanion is treated as an **upstream actuator dependency**, not as Sol's architecture. Sol Agent owns the stable command vocabulary, safety rules, acknowledgements, state and recovery contract.

## Repository map

- `src/` — phone-side Python 3.9 agent and adapters
- `bin/` — local/rescue CLI
- `config/` — secret-free configuration examples
- `launchd/` — rootless Dopamine/Procursus launchd staging service
- `home-assistant/` — HA package/examples
- `docs/` — phone setup, protocol and upstream notes
- `tests/` — protocol/dispatcher tests
- `scripts/` — staging installer and health checks

## Migration rule

Nothing in the existing working stack gets removed merely because a replacement exists here. Install this **alongside** production, prove it repeatedly, test recovery, then promote deliberately.

## Security

This repository contains **no passwords, access tokens, SSH private keys, MQTT credentials, Home Assistant long-lived tokens, device PINs or recovery codes**. Runtime secrets live only on the device / Home Assistant and are ignored by Git.

RemoteCompanion's Web UI/API is intentionally **not required** by this design. Prefer its local `rc` CLI/UNIX-socket path. If the Web UI is ever enabled, keep it trusted-LAN-only; upstream currently documents it as plaintext and unauthenticated.

## Current upstream

Primary actuator candidate: [`saihgupr/remotecompanion`](https://github.com/saihgupr/remotecompanion). See `docs/UPSTREAM.md` for the pinned review point and install source.

## Canonical context

`Solvale404/sol-core` remains the durable operating/context repository. This repo is the implementation/deployment home for the independent phone control plane; avoid duplicating identity/history/state documents here.
