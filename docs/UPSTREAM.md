# Upstream Dependencies

## RemoteCompanion

Repository: `saihgupr/remotecompanion`

Reviewed upstream point: `44f4d3264d4679f937887b4c86f5e1b7c38af78d` (reviewed 29 Sep 2026).

At that point upstream documents:

- iOS 14–16+ support
- rootless support including Dopamine
- local `rc` CLI for device actions and queries
- Home Assistant integration
- native MQTT publish/subscribe triggers
- Web UI / Automations API on port 8080
- rootless package build/install support

Package-manager source:

```text
https://saihgupr.github.io/remotecompanion
```

### How Sol Agent uses it

Use RemoteCompanion as a **local low-level actuator** through `rc`. Sol Agent keeps its own stable action vocabulary and calls only an allow-listed subset.

We are deliberately **not** making RemoteCompanion's Web UI/API the trust boundary. Upstream warns that when enabled it uses plaintext local-network transport and requires no API authentication. Keep it disabled for normal Sol operation.

### Initial upstream commands we depend on

```text
rc app
rc is-locked
rc button home
rc lock
rc open <app>
rc type <text>
rc toast <title> [subtitle]
rc brightness <0-100>
rc volume <0-100>
rc flashlight <on|off|toggle>
rc wifi <on|off|toggle>
rc bluetooth <on|off|toggle>
rc dnd <on|off|toggle>
rc lpm <on|off|toggle>
rc shortcut -r <name> [-p <input>]
```

`shortcut.run` additionally requires the upstream dependency RemoteCompanion documents for Shortcuts execution (SpringCuts). Treat that capability as unavailable until tested on Sol.

## Existing Sol stack

`Solvale404/sol-core` currently contains the production-shaped resident phone agent, localhost bridge and operating state. `Solvale404/SolCompanion` contains the native iOS front-end/SiriKit work.

This new repository is not permission to delete or fork those systems blindly. The migration should extract/replace only components that improve independence and reliability.

## Pinning policy

Do not auto-upgrade jailbreak dependencies on the production phone.

For each upstream update:

1. review release/change notes
2. install/test in the staging path
3. run the critical test matrix
4. record the tested commit/tag here
5. only then promote
