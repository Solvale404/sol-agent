#!/bin/sh
set -eu

PREFIX="/var/jb"
DEST="${PREFIX}/var/mobile/SolAgentNext"
PLIST_NAME="com.solvale.sol-agent-next.plist"
PLIST_DEST="${PREFIX}/Library/LaunchDaemons/${PLIST_NAME}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root so the launch daemon can be installed." >&2
  exit 1
fi

if [ ! -d "${PREFIX}" ]; then
  echo "Expected a rootless jailbreak at /var/jb." >&2
  exit 1
fi

PYTHON="${PREFIX}/usr/bin/python3"
if [ ! -x "${PYTHON}" ]; then
  echo "Python 3 not found at ${PYTHON}." >&2
  exit 1
fi

mkdir -p "${DEST}/src" "${DEST}/bin" "${DEST}/runtime"
cp src/*.py "${DEST}/src/"
cp bin/solctl.py "${DEST}/bin/solctl.py"
chmod 755 "${DEST}/bin/solctl.py"

if [ ! -f "${DEST}/config.json" ]; then
  cp config/sol-agent.example.json "${DEST}/config.json"
  echo "Created ${DEST}/config.json from the example."
  echo "Edit MQTT credentials before loading the daemon."
fi
chmod 600 "${DEST}/config.json"

cp "launchd/${PLIST_NAME}" "${PLIST_DEST}"
chmod 644 "${PLIST_DEST}"
chown -R mobile:mobile "${DEST}"
chown root:wheel "${PLIST_DEST}" 2>/dev/null || true

if grep -q 'REPLACE_ON_DEVICE' "${DEST}/config.json"; then
  echo
  echo "Staged successfully, but NOT loading the service because config still has placeholders."
  echo "Edit: ${DEST}/config.json"
  echo "Then load with: launchctl bootstrap system ${PLIST_DEST}"
  exit 0
fi

echo
printf "Load staging service now? [y/N] "
read answer
case "${answer}" in
  y|Y|yes|YES)
    launchctl bootout system/${PLIST_NAME%.plist} 2>/dev/null || true
    launchctl bootstrap system "${PLIST_DEST}"
    echo "Loaded ${PLIST_NAME%.plist}."
    ;;
  *)
    echo "Staged only. Load later with: launchctl bootstrap system ${PLIST_DEST}"
    ;;
esac
