# MyCareer Compass Backend API

Base path: `/api`

JSON requests use `Content-Type: application/json`. Authenticated calls use:

```http
Authorization: Bearer <token>
```

## Authentication

`POST /api/auth/login`

```json
{
  "login_id": "MMT001",
  "role": "employee",
  "password": "Raman"
}
```

Roles: `admin`, `zm`, `rd`, `employee`. Login IDs come from Employee Darwin. Passwords are the first name with its first letter capitalized. Passwords are stored as PBKDF2 hashes, not plain text. Role is part of account identity, so Dinesh Babu can use `MMT11043` independently in the ZM and RD portals.

`POST /api/auth/logout`

`GET /api/me`

## Public metadata

- `GET /api/health`
- `GET /api/meta` — seven competencies, exact rubric, available role-play links, terminology.

## Admin

- `GET /api/phases`
- `GET /api/admin/overview`
- `POST /api/admin/phases/open` — `{"phase":"rd","override":false}`
- `POST /api/admin/phases/close` — `{"phase":"rd"}`
- `GET /api/admin/confidence?employee_code=MMT001`
- `POST /api/admin/career/reset` — `{"employee_code":"MMT001"}`
- `POST /api/admin/linkedin/sync`
- `GET /api/admin/audit?limit=100` — persisted activity from exactly three active agents.

Phase order: `zm` → `rd` → `employee`. Opening a next phase requires 100% completion unless `override` is explicitly true.

## ZM and RD

- `GET /api/employees` — returns only role-scoped employees.
- `GET /api/employee-summaries` — scoped employees plus ZM/RD, role-play, final-profile, and aspiration status.
- `GET /api/final-profile?employee_code=MMT001` — final RD profile, subject to hierarchy scope.
- `GET /api/assessment?employee_code=MMT001`
- `POST /api/assessment`

```json
{
  "employee_code": "MMT001",
  "ratings": {
    "Communication": "Intermediate",
    "Stakeholder Management": "Proficient",
    "Ownership & Accountability": "Intermediate",
    "Team Management": "Beginner",
    "Executive Presence": "Intermediate",
    "Consultative Selling": "Proficient",
    "Data Analytics": "Intermediate"
  },
  "notes": {},
  "submit": true
}
```

Submitted assessments are locked. RD submissions become final competency profiles.

RD-only validation context:

- `GET /api/rd/validation?employee_code=MMT001`

This returns ZM ratings, final/draft RD ratings, rubric, and competency-specific TNA/Appraisal/Interview/Amber evidence. Missing evidence returns “No relevant evidence found.” Variable Pay is never loaded.

## Employee role plays and Career Lattice

- `GET /api/employee/roleplays`
- `POST /api/employee/roleplays`

```json
{
  "competency": "Communication",
  "filename": "communication.png",
  "content_base64": "<base64 image>"
}
```

Unreadable evidence returns `reupload_required`; no default proficiency is assigned.

- `GET /api/employee/career`
- `POST /api/employee/career` — `{"aspiration_role":"kam"}`

Career aspiration locks after submission. Admin reset is required for a change.

## Courses and learning

- `POST /api/employee/courses/generate`
- `GET /api/employee/courses`
- `POST /api/employee/learning/checkout` — `{"course_ids":["123","456"]}`
- `GET /api/employee/learning`

Backend course-level filter runs before Course Recommendation Agent:

- Beginner → `beginner`, `beginner_intermediate`
- Intermediate → `beginner_intermediate`, `intermediate`
- Proficient → `advanced`
- Advanced → `advanced`
- `general` excluded

Agent receives at most 15 filtered candidates per competency and returns two. Checkout requires at least one selected course per recommended competency.

Each recommended course exposes `title`, `url`, `provider`, `duration`, `competency`, `source_type`, and
`supported_proficiency_movement: {"from":"Beginner","to":"Intermediate"}`. The source catalog remains LinkedIn Learning.

## Leaderboard

`GET /api/leaderboard`

Scope follows authenticated role. Employees are grouped by equal total proficiency-level gap. Ranking uses LinkedIn Learning API hours only. Equal hours share rank.

## Active agents

Only these agents run:

1. Evidence Curator Agent
2. Role-play Assessment Agent
3. Course Recommendation Agent

Gap calculations, confidence, phase completion, aspiration locks, checkout validation, and leaderboard ranking are deterministic backend logic.
