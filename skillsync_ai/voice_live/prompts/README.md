# Voice Live roleplay prompts

Prompt files loaded by `skillsync_ai.voice_live.load_prompt(kind)`:

| File | Kind | Persona | Competencies scored |
|------|------|---------|---------------------|
| `functional.md` | `functional` | Placeholder stakeholder | Consultative Selling, Data Analytics, Stakeholder Relationship |
| `behavioural.md` | `behavioural` | **Sarah Patel**, Senior PM | Communication, Ownership & Accountability, Team Management, Executive Presence |

## Prompt style (Hotels-VoiceBot pattern)

Mirror `Hotels-VoiceBot` agent instruction structure:

1. **Role & Objective** — who the voicebot is, what success means
2. **Personality & Tone** — length, pacing (slightly brisk, never rushed); start first turn in English, then let the model handle language naturally
3. **Instructions / Rules** — turn-taking, unclear audio, hard constraints
4. **Staged conversation flow** — internal stages with strong/weak branches
5. **Silent observation guide** — rubrics never spoken aloud

Scoring is **not** spoken. After the call, `scoring_instruction(kind)` forces JSON ratings only.
 
## Behavioural scenario

**Title:** Leading a Cross-Functional Strategic Project  

Learner = Business Development Manager (Project Lead, no formal authority).  
AI = Sarah Patel (Product / Engineering / Delivery representative).  

Stakeholder-management behaviours in the scenario map to **Executive Presence** for product skill alignment (lattice / `ROLEPLAY_BUCKETS`).

## Editing rules

- Keep turns to 2–3 sentences + **one** question.
- Never reveal stages, rubrics, or competency names mid-call.
- Do not add tools or transfer flows (unlike Hotels-VoiceBot).
- Product skill names in `ROLEPLAY_BUCKETS` must match scoring JSON keys exactly.
