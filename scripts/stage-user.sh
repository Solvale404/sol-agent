#!/bin/sh
# Stage Sol Agent entirely inside mobile-owned paths. Does not touch launchd.
set -eu

PREFIX="/var/jb"
DEST="${PREFIX}/var/mobile/SolAgentNext"

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
  echo "Created ${DEST}/config.json from the safe local-only example."
fi
chmod 600 "${DEST}/config.json"

"${PYTHON}" -m compileall -q "${DEST}/src" "${DEST}/bin"

echo "Staged ${DEST}."
echo "No launch daemon was installed or changed."
echo "Local-only smoke run:"
echo "  ${PYTHON} ${DEST}/src/agent.py --config ${DEST}/config.json"
echo "Then in another shell:"
echo "  ${PYTHON} ${DEST}/bin/solctl.py status"
