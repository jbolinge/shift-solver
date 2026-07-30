---
id: scheduler-37
title: "Web UI"
type: task
status: closed
priority: 4
created: 2026-01-22
updated: 2026-07-30
parent: scheduler-35
depends-on: scheduler-36
---

# Web UI

Web-based user interface for schedule management.

## Features
- [ ] Dashboard with schedule overview
- [ ] Worker management (CRUD)
- [ ] Shift type configuration
- [ ] Schedule generation with progress
- [ ] Interactive schedule editing
- [ ] Availability calendar

## Technology
TBD: React/Vue/HTMX based on future decision

## Resolution

Closed as wontfix (2026-07-30): the application is scoped to the CLI and
solver engine only. The Django web UI experiment was removed on
feature/frontend-rewrite.
