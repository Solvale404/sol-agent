# Phone Setup — Staging

Target baseline: rootless Dopamine/Procursus, Python 3.9+, OpenSSH, existing Sol production stack left intact.

## 1. Install RemoteCompanion

Add this source in Sileo/Zebra:

```text
https://saihgupr.github.io/remotecompanion
```

Install RemoteCompanion. For the first pass:

- keep RemoteCompanion **Web UI off**
- do not bind experimental hardware gestures
- do not enable persistent foreground/camera automations
- do not change existing Sol launch daemons

Verify locally on the phone over SSH:

```sh
rc app
rc is-locked
rc toast "Sol staging" "RemoteCompanion local path works"
```

Then verify safe control actions one at a time:

```sh
rc button home
rc open calculator
rc volume 30
```

## 2. Get Sol Agent onto the phone

Preferred staging checkout:

```sh
cd /var/jb/var/mobile
git clone https://github.com/Solvale404/sol-agent.git SolAgentRepo
cd SolAgentRepo
```

If the repository is later made private, use an authenticated Git/SSH method instead of embedding a token in a clone URL.

## 3. Stage, don't replace

From the checkout:

```sh
su -
cd /var/jb/var/mobile/SolAgentRepo
sh scripts/install-stage.sh
```

This installs into:

```text
/var/jb/var/mobile/SolAgentNext
```

and uses the launchd label:

```text
com.solvale.sol-agent-next
```

It does not overwrite the current `/var/jb/var/mobile/SolAgent` production directory.

## 4. Runtime config

Edit:

```text
/var/jb/var/mobile/SolAgentNext/config.json
```

Set the Home Assistant MQTT broker host and the dedicated Sol MQTT username/password. Then:

```sh
chown mobile:mobile /var/jb/var/mobile/SolAgentNext/config.json
chmod 600 /var/jb/var/mobile/SolAgentNext/config.json
```

Do not commit this file.

## 5. Load the staging daemon

```sh
launchctl bootstrap system /var/jb/Library/LaunchDaemons/com.solvale.sol-agent-next.plist
```

Check:

```sh
launchctl print system/com.solvale.sol-agent-next
```

Logs:

```sh
tail -f /var/jb/var/mobile/SolAgentNext/runtime/stderr.log
```

## 6. Local rescue test before Home Assistant

```sh
/var/jb/usr/bin/python3 /var/jb/var/mobile/SolAgentNext/bin/solctl.py status
/var/jb/usr/bin/python3 /var/jb/var/mobile/SolAgentNext/bin/solctl.py caps
/var/jb/usr/bin/python3 /var/jb/var/mobile/SolAgentNext/bin/solctl.py toast "Sol Agent" "local rescue path works"
```

This path is deliberately independent of Home Assistant, MQTT, the Mac and the internet.

## 7. Unload staging instantly

```sh
launchctl bootout system/com.solvale.sol-agent-next
```

The existing production Sol services should remain untouched.

## Full reboot boundary

Dopamine is semi-untethered. After a true device reboot, jailbreak-only services cannot return until Dopamine is manually re-applied. The target behaviour is:

```text
full reboot → manually re-apply Dopamine → launchd automatically restores Sol Agent
```

That sequence must be tested before promotion.
