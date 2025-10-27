# AGI Assistant: Local AI Dashcam for Workflow Automation

[![Hackathon](https://img.shields.io/badge/Hackathon-AGI%20Assistant-blue)](https://github.com/HumanityFounders/The-AGI-Assistant) [![Local-Only](https://img.shields.io/badge/Privacy-Local%20Only-green)](https://example.com/privacy) [![Docker](https://img.shields.io/badge/Tech-Docker%20%2B%20FastAPI-orange)](https://docker.com)

A **desktop-based AI assistant MVP** that **observes** your screen/audio, **understands** workflows via local LLMs, **stores** patterns in SQLite, and **automates** tasks using PyAutoGUI. Built for the [Humanity Founders Hackathon](https://github.com/HumanityFounders/The-AGI-Assistant). Everything runs **locally**—no cloud, full privacy.

## 🎯 Overview & Hackathon Fit
- **Observe**: Screen/audio capture → OCR/STT processing → Structured JSON.
- **Understand**: Phi-3 analyzes for patterns → Stores in DB → Suggests automations.
- **Act**: Loads workflows from DB → Executes via PyAutoGUI → Verifies & refines.
- **Smart Data Mgmt**: Auto-purge old clips after pattern stability (e.g., 5 runs).
- **Round 1**: Dashcam MVP (capture + JSON insights).
- **Round 2**: Full agent (automation loop).

**Architecture Diagram**:
[GUI .exe] ↔ HTTP ↔ [Docker Backend]
├── Ollama (Phi-3, Pixtral OCR)
├── OCR Service (FastAPI)
├── STT Service (faster-whisper)
└── DB Service (SQLite + SQLAlchemy)
↓ (Mounted Volume)
[Local /data/: DB, Clips, JSON]


## 🚀 Quick Start
See [QUICKSTART_DAY1.md](QUICKSTART_DAY1.md) for <10min setup.

1. Clone/Fork this repo.
2. Install [Docker Desktop](https://docker.com).
3. Copy `.env.example` to `.env` and edit if needed.
4. `bash scripts/setup.sh` (builds + starts services, downloads models).
5. Build GUI: `pip install -r requirements_main.txt && pyinstaller ...` (full in guide).
6. Run `./dist/AGI_Assistant.exe`.

## 🏗️ Tech Stack
| Component | Tech | Why |
|-----------|------|-----|
| GUI | CustomTkinter + PyInstaller | Native .exe, modern UI |
| LLM | Ollama (Phi-3) | Local reasoning |
| OCR | Pixtral-12B via Ollama | Free vision OCR |
| STT | faster-whisper | Offline, fast |
| Services | FastAPI | Async APIs |
| DB | SQLite + SQLAlchemy | Local persistence, auto-purge |
| Automation | PyAutoGUI | Simple local actions |
| Orchestration | Docker Compose | Portable backend |

## 📖 Full Guides
- [Day 1 Guide](DAY1_GUIDE.md): Backend build (8-10hrs).
- [Commands Cheat Sheet](COMMANDS_CHEATSHEET.md): Docker ops.
- [DB Schema](services/db/DB_SCHEMA.md): (In services folder).

## 🧪 Testing
- Backend: `bash scripts/test_services.sh`.
- End-to-End: Record screen → Check `/data/` for JSON → Automate sample workflow.
- Demo: See [DEMO_SCRIPT.md](DEMO_SCRIPT.md) (TBD).

## 🔧 Troubleshooting
- **Ollama slow?** Pre-pull models: `bash scripts/download_models.sh`.
- **DB not persisting?** Check `./data/agi_assistant.db` exists (chmod 777 if perms issue).
- **Port conflicts?** Edit `docker-compose.yml` ports.
- **Windows?** Use Git Bash for scripts; ensure Docker WSL2.
- Logs: `docker-compose logs -f <service>` or `./logs/`.

## 🤝 Contributing
Fork → Branch → PR. Focus: Add GUI tabs, refine purge logic, more automations.

## 📄 License
MIT. For hackathon use only—contact [Humanity Founders](https://github.com/HumanityFounders/The-AGI-Assistant) for production.

**Built with ❤️ for the AGI era. Watch, Learn, Act.**