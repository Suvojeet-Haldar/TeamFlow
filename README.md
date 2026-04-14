# TeamFlow 🚀
### Multi-Tenant SaaS Project Management Platform

[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.0.4-green)](https://djangoproject.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live-Demo-brightgreen)](https://teamflow.fly.dev)

A production-grade web application enabling organizations to manage teams, delegate tasks, and monitor project workflows in real time.

---

## 🧩 Problem It Solves

Teams working across multiple projects struggle with task visibility, accountability, and workflow bottlenecks. TeamFlow provides a centralized platform where project managers can delegate, track, and analyze work — with real-time updates so nothing falls through the cracks.

---

## ✨ Features

- **Multi-Tenancy** — isolated workspaces per organization
- **Role-Based Access Control** — Owner, Project Manager, and Member permission tiers
- **Real-Time Kanban Board** — live drag-and-drop task management via WebSockets
- **Task Management** — create, assign, prioritize, archive tasks with full activity logs
- **Project Analytics** — task completion rates, workload distribution, overdue tracking
- **Activity Logging** — per-task change history split by change type
- **Task Numbering & Badges** — Kanban column counters and unique task IDs
- **Session-Based Authentication** — secure auth using Django's built-in auth framework

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, Django 6.0.4 |
| Real-Time | Django Channels 4.2, Daphne, WebSockets |
| Message Broker | Upstash Redis (TLS, channels layer) |
| Database | Supabase PostgreSQL (production), SQLite (dev fallback) |
| File Storage | Cloudflare R2 (`teamflow-media` bucket) |
| REST APIs | Django REST Framework |
| Containerization | Docker |
| Hosting | Fly.io (Mumbai region) |
| CI/CD | GitHub Actions → Fly.io auto-deploy on push to `main` |
| Frontend | HTML5, CSS3, JavaScript |

---

## 🏗️ Architecture

```
TeamFlow/
├── teamflow/          # Project config, ASGI, URL routing, settings
├── core/              # All app logic — models, views, consumers, templates
├── .github/workflows/ # CI/CD — GitHub Actions deploy pipeline
└── static/            # CSS, JS assets
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.13+
- Docker (for local container builds)
- A Supabase project (PostgreSQL)
- An Upstash Redis instance

### Installation

```bash
# Clone the repository
git clone https://github.com/Suvojeet-Haldar/TeamFlow.git
cd TeamFlow

# Create virtual environment
python -m venv env
source env/bin/activate  # Windows: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials (see Environment Variables below)

# Run migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

### Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for dev, `False` for production |
| `DJANGO_ENV` | `development` or `production` |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `DATABASE_URL` | Supabase PostgreSQL connection string |
| `DB_PASSWORD` | Database password |
| `REDIS_URL` | Upstash Redis TLS URL |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 access key |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 secret key |
| `R2_BUCKET_NAME` | R2 bucket name (`teamflow-media`) |
| `R2_ENDPOINT` | R2 endpoint URL |

---

## 🌐 Live Demo

[View Live on Fly.io](https://teamflow.fly.dev)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👤 Author

**Suvojeet Haldar**
- GitHub: [@Suvojeet-Haldar](https://github.com/Suvojeet-Haldar)
- LinkedIn: [suvojeet-haldar](https://linkedin.com/in/suvojeet-haldar-7b8a351aa)
- Email: suvojeethaldar4.work@gmail.com