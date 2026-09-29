# Parallel Migration Plan

Sol Agent is introduced **alongside** the current working Sol stack. No existing bridge, message path, control daemon or recovery mechanism is removed until the replacement is proven.

## Gate 0 — inventory and freeze

Before changing the phone:

- record current launchd jobs and ports
- record current working direct-control path
- record resident bridge health and Messages health
- confirm a rollback/reboot path
- take a copy of current production config without committing secrets

**Pass:** current production behaviour is known and reproducible.

## Gate 1 — install RemoteCompanion as an actuator

- add upstream package source: `https://saihgupr.github.io/remotecompanion`
- install RemoteCompanion through Sileo/Zebra
- leave its network Web UI/API **off**
- verify the local `rc` CLI
- prove a small safe set: status query, Home button, app open, toast, volume/brightness

Do not move existing production traffic yet.

**Pass:** `rc` works locally and does not break existing Sol services.

## Gate 2 — stage Sol Agent locally

Install this repo to the staging path:

`/var/jb/var/mobile/SolAgentNext`

Use the staging launchd label:

`com.solvale.sol-agent-next`

- copy `config/sol-agent.example.json` to runtime `config.json`
- enter MQTT credentials only in the runtime file
- set mode 600 on runtime config
- launch staging daemon
- run `solctl status` over the local UNIX socket

**Pass:** agent survives restart, reports health, and executes allow-listed actions only.

## Gate 3 — direct Home Assistant transport

- install/enable an MQTT broker in Home Assistant (Mosquitto is fine)
- create a dedicated Sol MQTT account
- configure Sol Agent to connect directly to the broker
- add the HA package/examples in `home-assistant/`
- verify retained availability, status and capabilities
- verify command acks

**Pass:** HA controls Sol without the Mac participating.

## Gate 4 — correctness and failure tests

Run `TEST_MATRIX.md` in order. Critical tests include:

- normal command + ack
- duplicate command id
- expired command
- malformed/unknown action
- screen locked
- Wi-Fi drop/rejoin
- broker restart
- HA restart
- Mac powered off
- internet disconnected
- respring
- userspace reboot
- full reboot → re-apply Dopamine → automatic staging-agent return
- direct SSH + `solctl` rescue with HA unavailable

**Pass:** critical tests are repeatable, not one-off successes.

## Gate 5 — messaging preservation

Existing direct Sol messaging remains production during the control-plane migration.

Only migrate messaging components when the replacement can demonstrate:

- allow-listed inbound sender handling
- at-most-once outbound semantics
- no duplicate reply regression
- bounded action verification
- no dependency on the Mac for the chosen production lane

**Pass:** the new lane meets or improves the current reliability contract.

## Gate 6 — promotion

Only after every critical gate passes:

1. take a final production snapshot
2. promote staging paths/names deliberately
3. leave the old service files available but unloaded for rollback
4. observe for at least several normal-use cycles
5. remove replaced plumbing last

## Immediate rollback

If staging causes unexpected UI capture, restart loops, duplicate messages, battery drain, or control loss:

1. unload `com.solvale.sol-agent-next`
2. stop its process
3. leave existing production services untouched
4. revert HA automations to the known-good route
5. investigate from logs before retrying

**Foreground rule:** no agent may repeatedly reclaim an app or undo a user's attempt to leave an app. Human foreground control always wins.
