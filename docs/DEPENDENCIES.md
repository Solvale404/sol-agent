# Dependencies and Acquisition Map

The goal is to add as little new jailbreak plumbing as possible.

## Already present / expected on Sol

These are part of the known working Sol baseline and should be verified, not blindly reinstalled:

| Component | Why | Action |
|---|---|---|
| Dopamine rootless jailbreak | jailbreak boundary | keep existing |
| Procursus/rootless userspace | `/var/jb` runtime | keep existing |
| Python 3.9.x | Sol Agent runtime | keep existing |
| OpenSSH | authenticated rescue/deployment | keep existing |
| existing Sol resident stack | production + rollback | do not remove |
| existing localhost Sol bridge | optional high-level adapter | preserve during migration |
| iOS-MCP | optional direct UI actuator | preserve during migration |

## New phone dependency

### RemoteCompanion

Source:

```text
https://saihgupr.github.io/remotecompanion
```

Upstream code:

```text
https://github.com/saihgupr/remotecompanion
```

Purpose: supply the low-level iOS actions/queries so Sol Agent does not reinvent jailbreak hooks.

Initial configuration:

- Web UI: **off**
- API/Web server: **not a production dependency**
- hardware/gesture bindings: leave unchanged/off initially
- MQTT integration inside RemoteCompanion: not required for Sol Agent v1 (Sol Agent owns the MQTT contract)
- Home Assistant integration inside RemoteCompanion: not required for Sol Agent v1

We use the **local `rc` CLI** only at first.

## Conditional phone dependency

### SpringCuts

RemoteCompanion documents SpringCuts as required for its `rc shortcut -r ...` action. Do **not** install it just because it exists.

Install only if we decide `shortcut.run` is useful enough and the plain RemoteCompanion test shows that capability unavailable without it. All core v1 control can work without Shortcuts execution.

## Deployment convenience

### Git

Git on the phone is convenient for cloning/pulling `Solvale404/sol-agent`, but it is not a runtime dependency.

If Git is missing, deployment can be performed through authenticated SSH/SCP from a trusted machine. Do not install a package solely to satisfy an aesthetic architecture preference.

## Home Assistant side

### MQTT broker

Required for direct HA ↔ Sol normal control.

Recommended path: Home Assistant Mosquitto broker add-on if there is not already a reliable broker.

Create a **dedicated Sol account**. Do not reuse an administrator login or put the password in this repo.

## Python packages

**None required for v1.**

The agent, SQLite store, UNIX rescue socket and MQTT 3.1.1 client use the Python standard library. This is deliberate: no `pip install`, no PyPI availability dependency, and less to repair on a jailbroken iOS 15 device.

## Things we explicitly do not need

- another jailbreak
- a public HTTP endpoint
- a Mac relay for normal runtime
- another queue/task store
- another memory system
- a second Home Assistant instance
- Docker on the phone
- Node.js on the phone
- a generic remote shell API

Add a dependency only when a proven use case justifies it.
