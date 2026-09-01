# Casambi lighting control

Agentic (natural-language) control of the building's Casambi lighting, driven
through Claude Code. You say *"dim the sanctuary to 40%"*; Claude runs a CLI
command; the command reaches Casambi's cloud, which reaches a gateway in the
building, which drives the Bluetooth mesh.

```
You → Claude Code → casambi_ctrl.py → door.casambi.com (cloud)
                                     → gateway (Casambi app in building)
                                     → Bluetooth mesh → luminaires
```

## What you need (prerequisites)

1. **A Casambi network** already set up in the Casambi app — ✅ you have this.
2. **A gateway.** One phone/tablet in the building must run the Casambi app,
   stay powered/online, and be set as **Gateway** (in the app: network
   settings → *Gateway* → enable). Without a gateway, the cloud can read your
   config but cannot switch the lights. This device is what makes remote/agentic
   control possible.
3. **An API key** from Casambi — the one missing piece. See Step 1.
4. **Network admin credentials** — the email + password you use to administer
   the network in the Casambi app.

---

## Step 1 — Request the API key (do this first; it takes time)

API keys are issued by Casambi Support and availability is limited, so start
here. Email **support@casambi.com**. A draft you can send is in
[`REQUEST-EMAIL.md`](./REQUEST-EMAIL.md).

You want a **network-level** key/credentials for your own network (not a
site/user key managing many customers). When it arrives you'll have an
`X-Casambi-Key` value.

## Step 2 — Confirm the gateway is on

In the Casambi app on the in-building device: network settings → enable
**Gateway**. Keep that device plugged in and online. (Good candidates: a cheap
tablet mounted in a closet, or the same device that already runs other building
tech.)

## Step 3 — Install and configure

On the machine that will run the control (recommended: your existing Google
Cloud VM — always-on and private):

```bash
cd casambi
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env — paste the API key, network admin email + password
```

`.env` is **gitignored** and must never be committed or placed on the public
website. The API key + password control your building's lights.

## Step 4 — Log in and discover devices

```bash
python casambi_ctrl.py login        # authenticates, caches a session
python casambi_ctrl.py discover     # lists every unit, group and scene + ids
```

`discover` writes `devices.json` (also gitignored — it's your building's
layout). This catalog is how names like "Sanctuary" get mapped to device ids.
The **groups** and **scenes** you created in the Casambi app are the useful
handles for natural-language control, so name them clearly in the app
(e.g. group "Sanctuary", scene "Shabbat", scene "Cleanup").

## Step 5 — Control it

```bash
# one light
python casambi_ctrl.py set "Bimah Spot 1" --level 0.4
python casambi_ctrl.py off "Lobby Downlight"

# a group (a whole zone)
python casambi_ctrl.py group "Sanctuary" --level 0.4
python casambi_ctrl.py group "Social Hall" --level 1.0

# a scene you built in the app
python casambi_ctrl.py scene "Shabbat"

# tunable-white color temperature
python casambi_ctrl.py set "Sanctuary" --level 0.8 --kelvin 3000

# live status of everything
python casambi_ctrl.py state
```

Every control command accepts `--dry-run`, which prints the exact message
without connecting — use it to sanity-check name resolution **before** the key
even arrives:

```bash
python casambi_ctrl.py group "Sanctuary" --level 0.4 --dry-run
```

## Step 6 — Natural language through Claude

Once Steps 1–5 work, in a Claude Code session (with `.env` present) you just say:

> *"Dim the sanctuary to 40% and turn the lobby off."*

Claude reads [`CLAUDE.md`](./CLAUDE.md) + `devices.json`, then runs the right
`casambi_ctrl.py` commands. See `CLAUDE.md` for how that mapping works.

---

## Security notes

- This directory lives in a **public** repo. The *code* is safe to publish; the
  **secrets are not**. `.env`, `.casambi_session.json`, and `devices.json` are
  gitignored — keep it that way.
- Anyone with the API key + network password can control your lights. Treat
  them like the building keys.
- Prefer running control from your private VM, not from the public site or a
  browser.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `403` on login | API key wrong or not yet activated by Casambi. |
| `401` on login | Wrong network admin email/password. |
| Login OK, lights don't change | Gateway device offline or not set as gateway. |
| `No networks returned` | Credentials are for a different account, or key scope wrong. |
| Scene doesn't fire | Scene message format varies by network — see the note in `casambi_ctrl.py::cmd_scene`, adjust once and it'll stick. |

## Files

| File | Purpose | In git? |
|---|---|---|
| `casambi_ctrl.py` | the control CLI | yes |
| `requirements.txt` | Python deps | yes |
| `.env.example` | config template | yes |
| `README.md` / `CLAUDE.md` / `REQUEST-EMAIL.md` | docs | yes |
| `.env` | real secrets | **no (gitignored)** |
| `.casambi_session.json` | cached session id | **no (gitignored)** |
| `devices.json` | building layout catalog | **no (gitignored)** |
