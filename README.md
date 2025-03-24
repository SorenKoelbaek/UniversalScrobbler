# UniversalScrobbler (project name pending)

UniversalScrobbler is a personal exploration into reclaiming purpose in music consumption.  
It serves as a centralized backend for tracking and understanding your musical life across analog and digital experiences.

## 🎧 Why This Project Exists

In an age of streaming algorithms and passive listening, I found myself longing for a more intentional, meaningful way of engaging with music. I collect vinyl records — moments, memories, and music that matter — but still rely heavily on Spotify or other streaming services while on the go.

This project was born out of a frustration: my analog listening experiences were invisible, while my digital history was cluttered with background noise — like Spotify autoplaying into the void on my Hi-Fi when it wasn't even on.

UniversalScrobbler aims to bridge that gap.

## 🌍 Vision

- **Connect every listening context** — whether you're spinning vinyl in your vacation house or streaming a new release on your commute.
- **Bring clarity to consumption** — understand *what* you're listening to, *where*, and *why*.
- **Reclaim music as an experience**, not background noise.
- **Use Spotify as an exploration tool**, not a consumption metric.
- **Promote physical ownership** and support for artists through intentional collection.

This is a backend-first project intended to power a suite of tools for scrobbling, insights, and collection discovery — all driven by *your actual listening habits* and curated taste.
---
## ⚙️ Architecture Overview

UniversalScrobbler is built as a modular, production-grade application with a clear separation of concerns and strong architectural boundaries.

### Backend (FastAPI)

- Built using **FastAPI** and **SQLModel** with **Alembic** for migrations.
- Uses **PostgreSQL** with a normalized schema (3rd normal form) and `UUID` primary keys.
- Models are split into:
  - `sqlmodels/`: database models (`table=True`)
  - `appmodels/`: API-layer models using Pydantic for clean I/O contracts  
    (we never use SQLModel objects directly in REST or between layers).
- Business logic is organized in **service classes**, instantiated as **singletons**.
- App-level dependencies (e.g. `auth`, `database.py`) live in `dependencies/`.
- Custom scripts for background tasks or scheduled jobs live in `/scripts`  
  (but all logic still resides in services and is covered by Poetry).
- Settings handled via **Dynaconf** with `settings.toml` and `secrets.toml`.
- Logging and Dynaconf setup lives in `config.py`.
- Each router has its own file and is registered in `main.py`.

The backend is deployed as a **systemd service** (`uvicorn.service`)

### Frontend (React)

- Built using **React**, **MUI**, and **Context API**.
- Structured into `pages/`, `components/`, and `contexts/`.
- Environment-specific configs live in `.env.development` and `.env.production`.

### Deployment

- Deployed automatically on push to `dev` branch.
- React app is built and served from a folder directly on the hosting server.
- Backend runs separately via `uvicorn` with PostgreSQL as the data layer.
---

## 🛠️ Setup & Development

This project assumes a working local development environment with Python and Node.js installed.

### 📦 Prerequisites

- A running **PostgreSQL** service
- A new, blank database and a dedicated user
- Add connection info to `secrets.toml` (see `secrets.toml_template`)

---

### 🔧 Install & Run

Clone the repo and install dependencies:

#### Install backend dependencies
```bash
cd api
poetry install
```

#### Install frontend dependencies
```bash
cd ../ui
npm install
```
#### Start dev servers (backend + frontend concurrently)
```bash
make dev
```

### 🧪 Environment Notes
Backend is built with Poetry and uses Dynaconf for config.

Frontend uses npm and MUI, with env configs in .env.*.


