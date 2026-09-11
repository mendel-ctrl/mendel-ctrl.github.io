#!/usr/bin/env python3
"""
Casambi lighting control — web app.

A small Flask server that:
  * holds the secrets (API key + network password) server-side, never in the browser,
  * serves a mobile-friendly one-page UI (main lights + scene switcher),
  * exposes a tiny JSON API the page calls to actually control the lights.

The page builds its own buttons from the discovered catalog, so it always
matches your real Casambi network. Run it on your always-on VM.

    pip install -r requirements.txt
    python casambi_ctrl.py login && python casambi_ctrl.py discover   # once
    python app.py                                                     # serve

Environment (in casambi/.env, same file the CLI uses):
    CASAMBI_API_KEY / CASAMBI_EMAIL / CASAMBI_PASSWORD   (required)
    CASAMBI_APP_PIN     a shared PIN required to use the app (strongly recommended)
    CASAMBI_APP_HOST    bind address (default 0.0.0.0)
    CASAMBI_APP_PORT    port (default 8080)

DEMO mode (no key needed — for previewing the UI):
    CASAMBI_APP_DEMO=1 python app.py
"""

import json
import os
from pathlib import Path

from flask import Flask, jsonify, request, Response

import casambi_ctrl as cc

HERE = Path(__file__).resolve().parent
FAVORITES_FILE = HERE / "favorites.json"
CUSTOM_SCENES_FILE = HERE / "scenes.json"
UI_FILE = HERE / "ui.html"

DEMO = os.environ.get("CASAMBI_APP_DEMO") == "1"

app = Flask(__name__)


# --------------------------------------------------------------------------- #
# Demo catalog — lets you (and Claude) preview the UI before the network is live.
# --------------------------------------------------------------------------- #
DEMO_CATALOG = {
    "network_name": "Chabad Center (demo)",
    "units": [],
    "groups": [
        {"id": 1, "name": "Sanctuary", "type": "Group"},
        {"id": 2, "name": "Lobby", "type": "Group"},
        {"id": 3, "name": "Social Hall", "type": "Group"},
        {"id": 4, "name": "Entrance", "type": "Group"},
        {"id": 5, "name": "Kitchen", "type": "Group"},
    ],
    "scenes": [
        {"id": 1, "name": "Shabbat"},
        {"id": 2, "name": "Event"},
        {"id": 3, "name": "Cleanup"},
        {"id": 4, "name": "Goodnight"},
    ],
}

# App-defined "quick scenes": a name mapped to a list of zone levels. These work
# WITHOUT you building scenes in the Casambi app — they just set several groups
# at once. Real file: scenes.json (gitignored). This is the demo default.
DEMO_CUSTOM_SCENES = {
    "Regular": [
        {"group": "Sanctuary", "level": 0.85},
        {"group": "Lobby", "level": 1.0},
        {"group": "Social Hall", "level": 0.75},
        {"group": "Entrance", "level": 1.0},
    ],
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def load_favorites():
    """Optional: which groups/scenes are 'main'. Missing file => show everything."""
    if FAVORITES_FILE.exists():
        try:
            return json.loads(FAVORITES_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def load_custom_scenes():
    """App-defined quick scenes (name -> [{group, level, kelvin?}, ...])."""
    if DEMO:
        return DEMO_CUSTOM_SCENES
    if CUSTOM_SCENES_FILE.exists():
        try:
            data = json.loads(CUSTOM_SCENES_FILE.read_text())
            return {k: v for k, v in data.items() if not k.startswith("_")}
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def get_catalog():
    if DEMO:
        return DEMO_CATALOG
    return cc.load_catalog()


def pin_required():
    return bool(os.environ.get("CASAMBI_APP_PIN"))


def check_pin():
    """Return None if OK, or a Flask 401 response if the PIN is wrong/missing."""
    if not pin_required():
        return None
    supplied = request.headers.get("X-App-Pin", "")
    if supplied and supplied == os.environ["CASAMBI_APP_PIN"]:
        return None
    return jsonify({"error": "Wrong or missing PIN."}), 401


def do_control(msg):
    """Send one control message over the Casambi WebSocket (or pretend, in demo)."""
    if DEMO:
        return {"ok": True, "demo": True, "sent": msg}
    cfg = cc.get_config()
    session = cc.load_session(cfg)
    cc.send_ws(cfg, session, msg, dry_run=False)
    return {"ok": True, "sent": msg}


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return Response(UI_FILE.read_text(), mimetype="text/html")


@app.route("/api/config")
def api_config():
    """Tells the page whether a PIN is needed and the network name."""
    catalog = get_catalog()
    return jsonify(
        {
            "network_name": catalog.get("network_name", ""),
            "pin_required": pin_required(),
            "demo": DEMO,
        }
    )


@app.route("/api/catalog")
def api_catalog():
    err = check_pin()
    if err:
        return err
    try:
        catalog = get_catalog()
    except cc.CasambiError as exc:
        return jsonify({"error": str(exc)}), 400

    favorites = load_favorites()

    def pick(kind):
        items = catalog.get(kind, [])
        wanted = favorites.get(kind)
        if wanted:  # keep only favorites, in the given order
            by_name = {i["name"].lower(): i for i in items}
            return [by_name[w.lower()] for w in wanted if w.lower() in by_name]
        return items

    return jsonify(
        {
            "network_name": catalog.get("network_name", ""),
            "groups": pick("groups"),
            "scenes": pick("scenes"),
            "custom_scenes": [{"name": n} for n in load_custom_scenes().keys()],
        }
    )


@app.route("/api/group", methods=["POST"])
def api_group():
    err = check_pin()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    try:
        catalog = get_catalog()
        group = cc.resolve(catalog, "groups", data["name"])
        level = float(data.get("level", 1.0))
        kelvin = data.get("kelvin")
        msg = {
            "method": "controlGroup",
            "id": group["id"],
            "targetControls": cc.build_target_controls(level=level, kelvin=kelvin),
        }
        return jsonify(do_control(msg))
    except cc.CasambiError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # WebSocket / network hiccup
        return jsonify({"error": f"Control failed: {exc}"}), 500


@app.route("/api/scene", methods=["POST"])
def api_scene():
    err = check_pin()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    try:
        catalog = get_catalog()
        scene = cc.resolve(catalog, "scenes", data["name"])
        level = float(data.get("level", 1.0))
        msg = {"method": "controlScene", "id": scene["id"], "level": level}
        return jsonify(do_control(msg))
    except cc.CasambiError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Control failed: {exc}"}), 500


@app.route("/api/custom", methods=["POST"])
def api_custom():
    """Activate an app-defined quick scene: set several groups at once."""
    err = check_pin()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name", "")
    try:
        custom = load_custom_scenes()
        steps = custom.get(name)
        if steps is None:  # case-insensitive fallback
            for k, v in custom.items():
                if k.lower() == str(name).lower():
                    steps = v
                    break
        if steps is None:
            raise cc.CasambiError(f"No quick scene named '{name}'.")
        catalog = get_catalog()
        for step in steps:
            group = cc.resolve(catalog, "groups", step["group"])
            msg = {
                "method": "controlGroup",
                "id": group["id"],
                "targetControls": cc.build_target_controls(
                    level=float(step.get("level", 1.0)), kelvin=step.get("kelvin")
                ),
            }
            do_control(msg)
        return jsonify({"ok": True})
    except cc.CasambiError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Control failed: {exc}"}), 500


@app.route("/api/alloff", methods=["POST"])
def api_alloff():
    err = check_pin()
    if err:
        return err
    try:
        catalog = get_catalog()
        # Turn every group off. (A dedicated "all off" scene is cleaner if you make one.)
        for group in catalog.get("groups", []):
            msg = {
                "method": "controlGroup",
                "id": group["id"],
                "targetControls": cc.build_target_controls(level=0.0),
            }
            do_control(msg)
        return jsonify({"ok": True})
    except cc.CasambiError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Control failed: {exc}"}), 500


def main():
    host = os.environ.get("CASAMBI_APP_HOST", "0.0.0.0")
    port = int(os.environ.get("CASAMBI_APP_PORT", "8080"))
    cc.load_dotenv()
    if DEMO:
        print("Running in DEMO mode — no real lights will change.")
    elif not pin_required():
        print("WARNING: no CASAMBI_APP_PIN set — anyone who reaches this page can "
              "control the lights. Set CASAMBI_APP_PIN in .env.")
    print(f"Casambi app on http://{host}:{port}")
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
