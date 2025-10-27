# Docker Commands Cheat Sheet

## Basics
- Start all: `docker-compose up -d`
- Stop all: `docker-compose down`
- Restart: `docker-compose restart`
- View status: `docker-compose ps`
- Build services: `docker-compose build`

## Logs & Debug
- Follow logs (all): `docker-compose logs -f`
- Service logs: `docker-compose logs -f ocr`
- Exec shell: `docker exec -it agi_ocr sh`
- Health check: `docker-compose ps` (look for "healthy")

## Models & Data
- Pull models: `bash scripts/download_models.sh`
- Backup DB: `cp data/agi_assistant.db data/backup_$(date +%Y%m%d).db`
- Purge volumes: `docker-compose down -v` (⚠️ Deletes data!)

## Tests
- All tests: `bash scripts/test_services.sh`
- DB query: `docker exec agi_db sqlite3 /app/data/agi_assistant.db "SELECT * FROM observations LIMIT 5;"`

## Aliases (Add to ~/.bashrc)
alias dcup='docker-compose up -d'
alias dcl='docker-compose logs -f'
alias dcdb='docker exec agi_db sqlite3 /app/data/agi_assistant.db'

**Pro Tip**: For demo, `docker-compose up` (foreground) to show startup.