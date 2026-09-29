#!/bin/sh
# Read-only preflight for Sol's phone. Prints no configured secrets.
set -u

section() { printf '\n== %s ==\n' "$1"; }
probe() { printf '%-28s' "$1"; shift; if "$@" >/tmp/sol-preflight.$$ 2>&1; then printf 'OK  '; else printf 'WARN'; fi; printf '  '; head -n 1 /tmp/sol-preflight.$$ 2>/dev/null || true; rm -f /tmp/sol-preflight.$$; }

section "identity"
printf 'uid/user: '; id
printf 'kernel:   '; uname -a
printf 'rootless: '; [ -d /var/jb ] && echo yes || echo no

section "runtime"
probe "python3" /var/jb/usr/bin/python3 --version
if command -v git >/dev/null 2>&1; then probe "git" git --version; else echo "git                         OPTIONAL  not installed"; fi
if command -v ssh >/dev/null 2>&1; then probe "ssh client" ssh -V; else echo "ssh client                  WARN  not found"; fi

section "existing Sol production"
if [ -d /var/jb/var/mobile/SolAgent ]; then
  echo "production dir              OK  /var/jb/var/mobile/SolAgent"
else
  echo "production dir              WARN  not found"
fi
if launchctl print system/com.solvale.agent >/dev/null 2>&1; then
  echo "com.solvale.agent           OK  loaded"
else
  echo "com.solvale.agent           INFO  not visible in system launchd domain"
fi
if launchctl print system/com.solvale.messageingest >/dev/null 2>&1; then
  echo "message ingest              OK  loaded"
else
  echo "message ingest              INFO  not visible in system launchd domain"
fi

section "RemoteCompanion"
RC=""
for p in "$(command -v rc 2>/dev/null || true)" /var/jb/usr/local/bin/rc /var/jb/usr/bin/rc /usr/local/bin/rc /usr/bin/rc; do
  [ -n "$p" ] || continue
  if [ -x "$p" ]; then RC="$p"; break; fi
done
if [ -n "$RC" ]; then
  echo "rc binary                   OK  $RC"
  probe "rc foreground app" "$RC" app
  probe "rc lock query" "$RC" is-locked
else
  echo "rc binary                   NEW  RemoteCompanion not installed/found"
fi

section "staging collision check"
[ -e /var/jb/var/mobile/SolAgentNext ] && echo "staging dir                 EXISTS  inspect before installing" || echo "staging dir                 CLEAR"
[ -e /var/jb/Library/LaunchDaemons/com.solvale.sol-agent-next.plist ] && echo "staging plist               EXISTS  inspect before installing" || echo "staging plist               CLEAR"

section "network prerequisites"
if command -v ping >/dev/null 2>&1; then
  probe "HA hostname DNS/LAN" ping -c 1 -W 2 homeassistant.local
else
  echo "ping                        INFO  unavailable; test broker later"
fi

section "result"
echo "Preflight complete. This script made no persistent changes."
