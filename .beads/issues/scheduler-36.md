---
id: scheduler-36
title: "REST API with FastAPI"
type: task
status: open
priority: 4
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-35
depends-on: scheduler-29
---

# REST API with FastAPI

RESTful API for web UI and integrations.

## Endpoints
- [ ] GET/POST /workers
- [ ] GET/POST /shift-types
- [ ] GET/POST /schedules
- [ ] POST /schedules/{id}/generate
- [ ] GET /schedules/{id}/validate
- [ ] WebSocket for solve progress

## Requirements
- FastAPI with Pydantic models
- OpenAPI documentation
- Authentication (future)
