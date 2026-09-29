# Sol Agent Test Matrix

Record each run with date, agent commit, RemoteCompanion commit/version, iOS state and result. A single green run is not a promotion gate.

| ID | Test | Expected result | Critical |
|---|---|---|:---:|
| T01 | `solctl status` with HA/MQTT unavailable | local response succeeds | ✅ |
| T02 | `system.ping` over MQTT | accepted/running/ok acks | ✅ |
| T03 | safe `ui.open` command | app opens once; final `ok` | ✅ |
| T04 | same command ID sent twice | action executes once; stored final ack returned | ✅ |
| T05 | expired command | no action; final `expired` | ✅ |
| T06 | unknown action | no subprocess; final `error` | ✅ |
| T07 | malformed JSON | rejected event; daemon remains healthy | ✅ |
| T08 | invalid argument (`volume=500`) | no action; final `error` | ✅ |
| T09 | screen locked | supported safe actions behave predictably | ✅ |
| T10 | Wi-Fi disconnect/rejoin | agent reconnects to broker without restart | ✅ |
| T11 | MQTT broker restart | LWT/offline visible; automatic reconnect + retained state | ✅ |
| T12 | Home Assistant restart | Sol remains alive; reconnect/control returns | ✅ |
| T13 | Mac powered completely off | HA ↔ Sol path still works | ✅ |
| T14 | internet/WAN disconnected | LAN MQTT + SSH rescue still work | ✅ |
| T15 | SpringBoard respring | agent/actuator recovery documented and repeatable | ✅ |
| T16 | userspace reboot | expected services recover without rebuild | ✅ |
| T17 | true phone reboot | after manual Dopamine re-apply, launchd restores staging agent | ✅ |
| T18 | HA unavailable | SSH into Sol + `solctl` control works | ✅ |
| T19 | RemoteCompanion unavailable | agent stays up; actuator actions fail boundedly | ✅ |
| T20 | 25 sequential commands | no duplicate execution or stuck `running` records | ✅ |
| T21 | rapid duplicate IDs | one execution only | ✅ |
| T22 | intentional daemon kill | launchd restarts it after throttle interval | ✅ |
| T23 | user manually exits foreground app | no automation forces it back open | ✅ |
| T24 | existing Sol Messages traffic during staging | no regression/duplication caused by staging | ✅ |
| T25 | runtime config permissions | `0600`, owner `mobile`; no secrets in repo/logs | ✅ |

## Latency capture

For control commands, record:

- HA/client publish → `accepted`
- `accepted` → final ack
- publish → visible device effect

Target optimisation order:

1. remove unnecessary orchestration hops
2. keep connection warm
3. bundle verification where appropriate
4. only then optimise actuator internals

Do not add preflight probes to every command unless data shows they improve reliability; they often make a fast path slower and more fragile.

## Promotion threshold

Before replacing any existing production path:

- all critical tests green
- T01/T02/T03/T04/T10/T13/T18 repeated at least 3 times
- reboot boundary T17 proven at least twice
- no duplicate-message regression
- no foreground-control incident
- rollback command/path verified immediately before promotion
