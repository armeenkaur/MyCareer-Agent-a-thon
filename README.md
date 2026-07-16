# MyCareer Compass Backend

Persistent backend for ZM assessment, RD validation, employee role plays, Career Lattice, course recommendations, learning journeys, LinkedIn Learning hours, and Admin controls.

## Run

```bash
/Users/int1961/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m skillsync_ai.app
```

Open:

- Wired Stitch frontend: http://127.0.0.1:5050/app/login
- Backend status: http://127.0.0.1:5050/
- API health: http://127.0.0.1:5050/api/health
- API metadata: http://127.0.0.1:5050/api/meta

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
