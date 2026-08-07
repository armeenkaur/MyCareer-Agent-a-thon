# Voice Live roleplay prompts

Prompt files loaded by `skillsync_ai.voice_live.load_prompt(kind)`:

| File | Kind | Persona | Strong skills (must rate) | Supporting (nullable) |
|------|------|---------|---------------------------|------------------------|
| `voice_naturalness.md` | *(shared)* | — | Prepended to every kind: natural turn-taking, anti-repeat, multi-point, Hindi mirror, Hotels unclear-audio | — |
| `functional.md` | `functional` | **Priya Nair** | Consultative Selling, Data Analytics, Stakeholder Relationship, Communication, Executive Presence | Ownership & Accountability, Team Management |
| `behavioural.md` | `behavioural` | **Sarah Patel** | Communication, Ownership & Accountability, Team Management, Executive Presence, Stakeholder Relationship | Data Analytics, Consultative Selling |

Source briefs: repo-root `help.md` (behavioural), `help2.md` (functional).

## Scoring (Option B — confidence-weighted merge)

Each roleplay rates **all 7** competencies:

```json
{"ratings":{"Communication":{"level":"Proficient","confidence":0.85},"Data Analytics":null,...}}
```

- `level`: Beginner | Intermediate | Proficient | Advanced
- `confidence`: 0.0–1.0 (evidence strength from Q volume + answer quality)
- Strong skills: object required. Supporting: `null` OK if no signal.
- Union of strong skills across both sessions = all 7 → **both-null cannot occur**.

After both sessions complete, `merge_roleplay_scores` writes one AI proficiency per skill:

`merged = Σ(level_value × confidence) / Σ(confidence)` → nearest level.

Partial (one session only): non-null skills written immediately; merge runs when the second completes.

## Prompt style

1. **Shared naturalness** (`voice_naturalness.md`) — Hotels-portable conversation craft
2. **Role & Objective** (kind file)
3. **Persona voice** (kind file)
4. **Timing / wrap** (kind file)
5. **Flexible topic areas** (not rigid Stage 1→N checklist)
6. **Silent observation guide**

Scoring is **not** spoken. After the call, `scoring_instruction(kind)` forces JSON ratings only.

## Editing rules

- Edit shared conversation behaviour in `voice_naturalness.md`.
- First audio turn = soft greeting only (`client.py` `_hello_payload`) — not a hardcoded script.
- Turn 2 = scenario context **without** re-introducing name/title.
- Continue sense-check is **prompt-driven** after ≥5 skills evidenced (no 3-minute clock).
- Never reveal stages, rubrics, or competency names mid-call.
- Do not add tools or transfer flows (unlike Hotels-VoiceBot).
- Product skill names in `ALL_ROLEPLAY_SKILLS` / `ROLEPLAY_BUCKETS` must match scoring JSON keys exactly.
