# Security Model

Sol Agent controls a real iPhone and may bridge into Home Assistant. Treat every network-facing surface as privileged.

## Non-negotiables

- No passwords, API keys, Home Assistant tokens, MQTT passwords, SSH private keys, device PINs or recovery codes in Git.
- No public port forwarding to Sol Agent, RemoteCompanion, iOS-MCP or Home Assistant.
- No generic `shell`, `exec`, `eval` or arbitrary subprocess action in the remote command vocabulary.
- Dynamic action arguments are passed as argument arrays with `shell=False` and validated before execution.
- Commands carry an id, source, timestamp and TTL.
- Duplicate command ids return the prior result instead of re-executing.
- Sensitive runtime config should be mode `0600` and owned by the `mobile` user.
- MQTT uses a dedicated account with only the required topic ACLs where the broker supports ACLs.
- SSH rescue uses key authentication; disable password login when practical after the key path is proven.

## Network surfaces

### Preferred

- **MQTT:** authenticated LAN/private-network transport between Home Assistant and Sol Agent.
- **SSH:** authenticated rescue/debug transport.
- **UNIX socket:** local `solctl` control on the phone.
- **RemoteCompanion `rc`:** local CLI talking to its local server/socket.

### Avoid as production dependencies

RemoteCompanion documents its Web UI/Automations API as plaintext and unauthenticated when enabled. Sol Agent therefore does not require that server. Keep it off unless performing a bounded trusted-LAN test.

The existing Sol resident bridge should remain bound to localhost unless there is a concrete reviewed reason to change that.

## Capability policy

The initial remote allow-list intentionally excludes destructive/high-impact system actions such as userspace reboot, ldrestart, respring, Safe Mode and arbitrary shell execution. These may be exposed later only as separately gated rescue capabilities with explicit policy.

Foreground/exclusive automation must be bounded and immediately escapable. Do not ship a persistent loop that forces Camera or another app back to the foreground.

## Runtime secret file

Copy `config/sol-agent.example.json` to a runtime-only `config.json`, fill credentials on-device, then:

```sh
chmod 600 config.json
```

The repository `.gitignore` excludes that filename.

## Compromise response

If MQTT credentials or a Home Assistant token are exposed:

1. disable/rotate the credential at the source
2. stop Sol Agent if necessary
3. verify broker/HA logs for unexpected commands
4. issue a new least-privilege credential
5. do not rewrite Git history unless a secret was actually committed; if it was, rotate first, then purge history
