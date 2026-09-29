# Sol Agent Protocol v1

Transport: MQTT 3.1.1, JSON payloads, QoS 0 initially. Reliability comes from command IDs + acknowledgements + retained state, not from blindly re-running commands.

Default topic prefix: `sol/v1`

## Topics

| Topic | Direction | Retained | Purpose |
|---|---|---:|---|
| `sol/v1/cmd` | HA/client → Sol | no | commands |
| `sol/v1/ack/<id>` | Sol → client | no | lifecycle/result for one command |
| `sol/v1/status` | Sol → clients | yes | current agent health summary |
| `sol/v1/capabilities` | Sol → clients | yes | named action manifest |
| `sol/v1/availability` | Sol → clients | yes | `online` / LWT `offline` |
| `sol/v1/events` | Sol → clients | no | bounded asynchronous events |

## Command envelope

```json
{
  "v": 1,
  "id": "ha-1727600000-4312",
  "action": "ui.open",
  "args": {"app": "calculator"},
  "sent_at": 1727600000.123,
  "ttl": 30,
  "source": "home-assistant"
}
```

Rules:

- `id`: 1–128 characters; unique per logical command.
- `action`: must exist in the published capability manifest.
- `args`: JSON object only.
- `sent_at`: Unix epoch seconds.
- `ttl`: 1–300 seconds; stale commands are rejected without execution.
- `source`: descriptive source label only; it is not an authorization primitive.

Broker authentication/ACLs are the authorization boundary. The agent still validates every action and argument.

## Acknowledgement lifecycle

The agent may emit:

1. `accepted`
2. `running`
3. final `ok`, `error`, or `expired`

Example final ack:

```json
{
  "v": 1,
  "id": "ha-1727600000-4312",
  "status": "ok",
  "action": "ui.open",
  "result": {"stdout": ""},
  "error": null,
  "finished_at": 1727600000.812
}
```

## Idempotency

Final results are persisted in SQLite by command ID. If a client retries an already-completed ID, Sol Agent returns the stored final acknowledgement and does **not** execute the action again.

If the daemon restarts with commands left in `accepted`/`running`, those records are finalized as an `error` with a restart marker rather than silently replayed.

## Initial action vocabulary

- `system.ping`
- `system.status`
- `system.capabilities`
- `ui.home`
- `ui.lock`
- `ui.open`
- `ui.type`
- `notify.toast`
- `device.brightness`
- `device.volume`
- `device.flashlight`
- `device.wifi`
- `device.bluetooth`
- `device.dnd`
- `device.low_power`
- `shortcut.run`
- `query.foreground_app`
- `query.locked`

Potentially disruptive actions such as respring/userspace reboot are intentionally absent from v1 remote control.
