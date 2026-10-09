# Architecture — sol-agent

Sol's self-contained resident iPhone agent and direct Home Assistant control path.

## Source components

src/, home-assistant/, scripts/, launchd/, tests/, MIGRATION.md, ARCHITECTURE.md, TEST_MATRIX.md.

## Interface

Resident iPhone service and local HA interface; no public hosted dashboard.

## Ownership and recovery

Repository already documents staging migration; do not treat code or passed tests as an installed replacement for Sol's existing stack.

This repository owns its project source. GitHub owns releases; Systems Hub cross-system architecture/history; ClickUp commitments; canonical Chat Queue async jobs/results/continuation.
