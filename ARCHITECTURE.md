# Architecture

## Boundary

Sol Agent is the **phone control plane**, not Sol's entire identity/memory/reasoning system.

Canonical operating context remains in `Solvale404/sol-core`. Existing Sol Messages, SolCompanion and resident bridge stay production until separately migrated.

## Planes

### 1. Transport plane

Primary: authenticated MQTT over the trusted LAN/private network.

Fallback/rescue: SSH into the phone and call `solctl`, which uses a local UNIX socket.

No Mac relay is required by either path.

### 2. Command plane

Sol Agent owns a versioned, stable action vocabulary. Remote callers cannot submit raw shell commands.

Each command is:

```text
validate → TTL check → dedupe → accepted → running → allow-listed dispatch → final ack → audit
```

Completed command IDs are persisted to SQLite so retries do not cause duplicate execution.

### 3. Actuator plane

Preferred low-level actuator: RemoteCompanion `rc` locally on the phone.

Why:

- already designed for modern rootless jailbreaks
- broad device/app actions
- local CLI/socket path avoids network API exposure
- reduces the amount of private jailbreak code Sol Agent has to own

Optional adapters remain possible for capabilities RemoteCompanion does not cover cleanly:

- existing Sol localhost bridge for Sol-specific high-level services
- iOS-MCP for bounded UI automation that genuinely requires coordinate/accessibility-style interaction

Adapters must remain behind named Sol Agent capabilities; callers should not need to know which actuator implements them.

### 4. State plane

Sol publishes retained:

- availability
- health/status
- capability manifest

The initial health model intentionally favors states we can verify cheaply and reliably. Do not add expensive probe chains merely to fill a dashboard.

### 5. Recovery plane

Expected failure behaviour:

| Failure | Expected behaviour |
|---|---|
| Mac off | no impact on HA ↔ Sol control |
| HA down | phone local agent remains alive; SSH + `solctl` rescue works |
| MQTT broker down | local agent remains alive and reconnects automatically |
| internet down | local MQTT/SSH continue |
| Wi-Fi interruption | broker reconnect loop restores transport |
| RemoteCompanion down | agent stays alive; only RC-backed actions fail boundedly |
| agent crash | launchd restarts after throttle interval |
| respring/userspace restart | staging recovery is tested before promotion |
| full reboot | user must re-apply Dopamine; launchd then restores jailbreak services |

## Why not expose RemoteCompanion's HTTP API directly?

It is useful for testing, but upstream currently documents the Web UI/Automations API as plaintext and unauthenticated. Putting a stable authenticated Sol Agent protocol in front of local actuators gives us:

- one security boundary
- consistent acknowledgements
- idempotency
- a capability manifest
- easier future actuator swaps
- less Home Assistant coupling to jailbreak internals

## Why a small in-repo MQTT client?

Sol already has Python 3.9. The initial MQTT client is deliberately stdlib-only so the transport does not depend on pip/package availability on the jailbroken phone.

It supports only the subset we need first: MQTT 3.1.1, authenticated CONNECT, QoS-0 publish/subscribe, retained messages, keepalive and LWT. If production evidence shows this is insufficient, replace the transport implementation behind the same protocol rather than changing HA callers.

## Messaging

Direct messaging is explicitly **out of scope for the first control-plane cutover**. The existing known-good Messages lane remains in place while Sol Agent proves device control/recovery.

When messaging is migrated later, it must preserve at-most-once outbound semantics and cannot claim an action succeeded without a verified executor result.

## Foreground ownership

No persistent app-reclaim loop is permitted. Camera/kiosk/foreground-exclusive experiments are separate, bounded, default-off and immediately escapable. Human foreground control always wins.
