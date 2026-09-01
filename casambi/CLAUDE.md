# Driving Casambi lighting from Claude Code

When the user asks to control the building's lights in this session, use the
`casambi_ctrl.py` CLI in this directory. This file tells you how to translate a
natural-language request into commands.

## Before acting

1. Ensure `casambi/.env` exists (or `CASAMBI_*` env vars are set). If not, tell
   the user to complete Step 1–3 in `README.md` (they need the API key first).
2. Make sure a catalog exists: read `casambi/devices.json`. If it's missing,
   run `python casambi_ctrl.py discover` first. This file maps the user's
   spoken names ("sanctuary", "lobby") to Casambi ids.

## Mapping requests to commands

Prefer **groups** and **scenes** over individual units — they map to how people
talk about zones and moods.

| The user says | Run |
|---|---|
| "turn the sanctuary to 40%" | `python casambi_ctrl.py group "Sanctuary" --level 0.4` |
| "lights off in the lobby" | `python casambi_ctrl.py group "Lobby" --level 0.0` |
| "full brightness everywhere" | one `group ... --level 1.0` per zone, or a scene |
| "set it to Shabbat mode" | `python casambi_ctrl.py scene "Shabbat"` |
| "warm the sanctuary to 3000K" | `python casambi_ctrl.py set "Sanctuary" --level 0.8 --kelvin 3000` |
| "what's on right now?" | `python casambi_ctrl.py state` |

Percent → level: divide by 100 (40% → `0.4`). Level is `0.0`–`1.0`.

## Rules

- **Resolve names from `devices.json`, don't invent ids.** If a name is
  ambiguous or absent, the CLI will say so — relay that and ask which zone the
  user means rather than guessing.
- **Confirm before anything disruptive** — turning everything off, or acting
  during an event — unless the user was explicit.
- **Dry-run when unsure.** Add `--dry-run` to preview the message and confirm
  you picked the right target before sending for real.
- **Report what happened.** After running, say which unit/group/scene you set
  and to what. If the CLI errored (403/401/offline gateway), relay the
  troubleshooting hint, don't retry blindly.
- Never print or commit the contents of `.env`.
