# MyCareer Compass Backend

Persistent backend for ZM assessment, RD validation, employee role plays, Career Lattice, course recommendations, learning journeys, LinkedIn Learning hours, and Admin controls.

## Run

```bash
python -m skillsync_ai.app
```

Open:

- Wired Stitch frontend: http://127.0.0.1:5050/app/login
- Backend status: http://127.0.0.1:5050/
- API health: http://127.0.0.1:5050/api/health
- API metadata: http://127.0.0.1:5050/api/meta

Binds `HOST` (default `0.0.0.0`) and `PORT` (default `5050`). Render sets `PORT` automatically.

### Render

1. New Web Service → this repo  
2. Build: `pip install -r requirements.txt`  
3. Start: `python -m skillsync_ai.app`  
4. Env: `OPENAI_API_KEY`, optional `OPENAI_MODEL`  
5. Open `https://<service>.onrender.com/app/login` (not bare `/` only)

Or use `render.yaml` in repo root.
Database: `data/mycareer.db` (created and seeded automatically; gitignored).

## Authentication seed

- Employee login ID: Darwin `EMP Code`
- ZM login ID: Darwin `Immediate Supervisor Code`
- RD login ID: Darwin `Skip Manager ID`
- Password: first name with first letter capitalized
- Admin: `ADMIN` / `Admin`

Passwords are PBKDF2-hashed. Account uniqueness is `(login_id, role)`, allowing one person to have separate ZM and RD accounts.

## Active agents

Only three agents run:

1. Evidence Curator Agent
2. Role-play Assessment Agent
3. Course Recommendation Agent

RD rating is final and never adjusted. Gap calculations, confidence, phase gates, course-level filtering, aspiration locking, checkout validation, and leaderboard ranking are deterministic.

See [API.md](API.md) for frontend integration contracts.

## Tests

```bash
/Users/int1961/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests -v
```
