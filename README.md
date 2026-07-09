# MyCareer Compass Agent-a-thon

This is a production-shaped Python web app for the BD skill profile and Level 2 skill-gap flow.

Run with the bundled Python runtime used by Codex:

```bash
/Users/int1961/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m skillsync_ai.app
```

To enable the live Groq behavioural evidence agent, set `GROQ_API_KEY` before starting:

```bash
export GROQ_API_KEY="your_groq_api_key_here"
/Users/int1961/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m skillsync_ai.app
```

Then open:

- Employee: http://127.0.0.1:5050/employee
- Manager: http://127.0.0.1:5050/manager
- Admin: http://127.0.0.1:5050/admin

All submissions and locks are in memory. Restarting the project clears form data and unlocks all forms.

## Architecture

```text
skillsync_ai/
  app.py                 # server entrypoint
  core/                  # config, paths, proficiency constants, helpers
  data_sources.py        # Excel ingestion and source-of-truth mapping
  state.py               # runtime form locks, uploads, profiles, logs
  agents/                # named agent implementations
  profile_pipeline.py    # orchestrates scoring, agents, confidence, gaps
  web/                   # HTTP routes, form posts, static serving, views
  templates/             # HTML shell
  static/                # CSS
```

Agent responsibilities:

- `Behavioural Evidence Agent`: scores uploaded role-play screenshots through Groq when configured, with demo fallback.
- `Feedback/TNA/Amber Agent`: interprets contextual evidence from the attached workbooks.
- `Skill Adjustment Agent`: applies evidence-backed profile adjustments.
- `Confidence Agent`: produces confidence only; it never changes skill scores.
- `Gap Agent`: compares the final profile with the ideal role/level matrix.
