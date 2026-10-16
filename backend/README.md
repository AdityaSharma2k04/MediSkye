---
title: MediSkye Backend
emoji: 🩺
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# MediSkye Backend API

FastAPI backend for MediSkye — an AI medical report interpreter.

Endpoints:
- `POST /register`, `POST /login` — auth
- `POST /upload` — upload PDF/image reports
- `POST /query` — SSE streaming Q&A
- `GET /health` — liveness

## Development Setup
Runtime only: `pip install -r requirements.txt`
Dev + runtime: `pip install -r requirements-dev.txt`
