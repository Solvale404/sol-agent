# Home Assistant Setup

Goal: Home Assistant talks directly to Sol over MQTT. The Mac is not a runtime hop.

## Broker

Use the Home Assistant Mosquitto broker add-on or another broker already trusted on the home LAN.

Create a dedicated account for Sol Agent instead of reusing an admin credential. If broker ACLs are enabled, Sol needs:

```text
subscribe: sol/v1/cmd
publish:   sol/v1/ack/#
publish:   sol/v1/status
publish:   sol/v1/capabilities
publish:   sol/v1/availability
publish:   sol/v1/events
```

Home Assistant needs the inverse publish/subscribe access.

Do not expose MQTT port 1883 directly to the public internet.

## Phone config

Set the broker host, port, username and password in the phone's runtime-only `config.json`.

Prefer a stable LAN hostname/IP for the broker. `homeassistant.local` is fine if mDNS is consistently reliable on the phone; otherwise use a reserved LAN address.

## HA package

`home-assistant/sol_agent.yaml` provides:

- one Sol status entity with JSON attributes
- one capabilities entity
- a generic `script.sol_agent_command`
- a few convenience scripts for smoke tests

The convenience scripts are backend plumbing, not the final UI. The intended dashboard is a **single unified Sol card** showing reachability/health and only contextually useful actions.

If packages are enabled, copy or merge the file into the HA package directory. Otherwise merge its `mqtt:` and `script:` sections into the appropriate config files.

## Smoke test

After Sol Agent connects, HA should see:

```text
sol/v1/availability = online
```

and retained JSON on:

```text
sol/v1/status
sol/v1/capabilities
```

Call `script.sol_agent_ping`, then inspect MQTT for an acknowledgement on:

```text
sol/v1/ack/<generated-command-id>
```

## Command example

```yaml
action: script.sol_agent_command
data:
  action: ui.open
  args:
    app: calculator
```

## Failure behaviour

- Broker down: Sol Agent keeps its local SSH/`solctl` rescue path and reconnects to MQTT.
- HA down: Sol Agent remains alive; direct SSH/`solctl` still works.
- Mac down: no effect on this control path.
- Internet down: local MQTT + SSH should continue.
- Phone reboot: re-apply Dopamine, then launchd should restore the agent automatically.
