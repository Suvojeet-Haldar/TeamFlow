# TeamFlow

> **Production-deployed, multi-tenant SaaS project management platform with real-time collaboration via WebSockets.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-teamflow.fly.dev-blue?style=for-the-badge&logo=fly.io)](https://teamflow.fly.dev)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.0.4-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://supabase.com)
[![Redis](https://img.shields.io/badge/Redis-Upstash-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://upstash.com)

---

## Overview

TeamFlow is a multi-tenant project management platform with real-time Kanban-style task tracking, role-based access control, and secure file attachments — all served from a single production-grade ASGI deployment.

The platform is built on **Django Channels** with Redis as the channel layer, handling WebSocket race conditions that arise when multiple users simultaneously drag tasks across concurrent board views. The server runs **Daphne** (ASGI), not Gunicorn, maintaining persistent WebSocket connections alongside standard HTTP traffic.

**Live:** [https://teamflow.fly.dev](https://teamflow.fly.dev)

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | Django 6.0.4, Django REST Framework |
| **Real-time / ASGI** | Django Channels, Daphne, WebSockets |
| **Channel Layer** | Redis (Upstash, TLS — `rediss://`) |
| **Database** | PostgreSQL via Supabase |
| **Object Storage** | Cloudflare R2 (S3-compatible), django-storages + boto3 |
| **Auth** | Custom User model (`core.CustomUser`), session auth, RBAC |
| **Infrastructure** | Docker, Fly.io |
| **CI/CD** | GitHub Actions → `flyctl deploy` on push to `main` |

---

## Architecture

```
TeamFlow/
├── teamflow/          # Project config — settings, ASGI, URL routing
├── core/              # App logic — models, views, consumers, templates
├── .github/workflows/ # CI/CD — GitHub Actions → Fly.io deploy pipeline
└── Dockerfile         # Daphne ASGI entrypoint, collectstatic build step
```

**Request flow:**

```
Browser
  │
  ├── HTTPS  →  Fly.io Global Proxy  →  Daphne (ASGI)
  │                                         ├── HTTP  →  Django Views / DRF
  │                                         └── WS    →  Django Channels
  │                                                          └── Redis Channel Layer
  │                                                                  └── Broadcast to group
  │
  └── Static Assets  →  /app/staticfiles  (collected at build time via Dockerfile)
```

---

## Key Engineering Decisions

**Daphne over Gunicorn** — Django Channels requires an ASGI server to handle WebSocket protocol upgrades. Gunicorn is WSGI-only; Daphne handles both HTTP and WS on the same port.

**Redis channel layer (Upstash)** — Django Channels uses Redis as a message broker to fan out WebSocket events across consumers. When a user drags a task, the consumer publishes to a project-scoped Redis group; all connected clients in that group receive the broadcast immediately.

**Supabase PostgreSQL** — Managed PostgreSQL with connection pooling. Row-level security is currently disabled (flagged for future hardening).

**Cloudflare R2** — S3-compatible object storage for task attachments and profile photos. Zero egress fees. Wired into Django via `storages.backends.s3boto3.S3Boto3Storage`.

**`python-decouple` for config** — All secrets consumed via `config()`, never hardcoded. Production secrets managed as Fly.io secrets.

---

## Features

- **Multi-tenant isolation** — organisations are fully isolated at the data layer; no cross-tenant access
- **Real-time Kanban board** — task drag-and-drop syncs instantly across all connected clients via WebSocket broadcast, with race condition handling for concurrent updates
- **Role-based access control (RBAC)** — owner, admin, and member roles with enforced view / edit / delete permission gates
- **File attachments** — task-level file uploads stored on Cloudflare R2 (S3-compatible object storage)
- **Profile photos** — user avatars served from R2 via `S3Boto3Storage`
- **Activity log** — per-project audit trail of all task state changes
- **Custom user model** — `core.CustomUser` as `AUTH_USER_MODEL`; no dependency on Django's built-in `auth_user` table
- **CI/CD pipeline** — zero-touch deploy via GitHub Actions on every push to `main`

---

## Local Development

### Prerequisites

- Python 3.12+
- PostgreSQL (or SQLite for local-only dev)
- Redis

### Setup

```bash
git clone https://github.com/Suvojeet-Haldar/TeamFlow.git
cd TeamFlow

python -m venv env

# Activate virtualenv
. env/Scripts/activate      # Git Bash on Windows
# source env/bin/activate   # Linux / macOS

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Run migrations and start the server:

```bash
python manage.py migrate
python manage.py createsuperuser

# Daphne (recommended — full HTTP + WebSocket support)
daphne -p 8000 teamflow.asgi:application

# Django dev server (also supports WebSockets via Channels)
python manage.py runserver
```

---

## Environment Variables

All secrets are consumed via `python-decouple` (`config()`). In production these are set as Fly.io secrets.

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DATABASE_URL` | PostgreSQL connection string (parsed by `dj-database-url`) |
| `REDIS_URL` | Redis connection string — use `rediss://` for TLS (Upstash) |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 access key |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 secret key |
| `R2_BUCKET_NAME` | R2 bucket name |
| `R2_ENDPOINT` | R2 S3-compatible endpoint URL |
| `ALLOWED_HOSTS` | Comma-separated allowed hostnames |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated CSRF-trusted origins |
| `DEBUG` | `False` in production |
| `DJANGO_ENV` | `production` / `development` |

---

## Deployment

Deployed on **Fly.io**. The CI/CD pipeline in `.github/workflows/deploy.yml` triggers `flyctl deploy` automatically on every push to `main`, using `FLY_API_TOKEN` stored as a GitHub Actions secret.

**Manual deploy:**

```bash
flyctl deploy
```

The `Dockerfile` runs `collectstatic` at build time, placing all static assets into `/app/staticfiles` inside the container.
