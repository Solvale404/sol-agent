# Development — sol-agent

**Local check:** Use the existing scripts and test matrix; no general-purpose live integration test performed.

Source checks are not physical phone tests or a deployment. Use branch → scoped test → PR → release → intentionally verified device/app update, with rollback.

**Safety:** Repository already documents staging migration; do not treat code or passed tests as an installed replacement for Sol's existing stack.
