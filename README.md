# TeamFlow 🚀
### Multi-Tenant SaaS Project Management Platform

[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.0.2-green)](https://djangoproject.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live-Demo-brightgreen)](https://your-render-url.onrender.com)

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
| Backend | Python 3.13, Django 6.0.2 |
| Real-Time | Django Channels, WebSockets |
| Cache / Message Broker | Redis (Memurai on Windows) |
| Database | PostgreSQL (production), SQLite (dev) |
| REST APIs | Django REST Framework |
| Deployment | Render, Gunicorn |
| Frontend | HTML5, CSS3, JavaScript |

---

## 🏗️ Architecture

```
TeamFlow/
├── teamflow/          # Project config, ASGI/WSGI, URL routing
├── core/              # All app logic — models, views, consumers, templates
└── static/            # CSS, JS assets
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.13+
- Redis (or Memurai on Windows)
- PostgreSQL

### Installation

```bash
# Clone the repository
git clone https://github.com/Suvojeet-Haldar/TeamFlow.git
cd TeamFlow

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database and Redis credentials

# Run migrations
python manage.py migrate

# Start Redis (or Memurai)
# Then start the development server
python manage.py runserver
```

---

## 🌐 Live Demo

[View Live on Render](https://your-render-url.onrender.com)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👤 Author

**Suvojeet Haldar**
- GitHub: [@Suvojeet-Haldar](https://github.com/Suvojeet-Haldar)
- LinkedIn: [suvojeet-haldar](https://linkedin.com/in/suvojeet-haldar-7b8a351aa)
- Email: suvojeethaldar4.work@gmail.com
