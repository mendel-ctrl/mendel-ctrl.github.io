#!/usr/bin/env python3
"""
Casambi lighting control CLI.

A small, self-contained command-line tool for controlling a Casambi Bluetooth
mesh lighting network through Casambi's cloud API. Designed to be driven either
by a person or by Claude Code translating natural-language requests
("dim the sanctuary to 40%") into concrete commands.

Flow:  this CLI  ->  Casambi cloud (door.casambi.com)  ->  gateway in building
       ->  Bluetooth mesh  ->  luminaires.

Secrets (API key + network password) come from environment variables, never
from source. See .env.example. Requires a phone/tablet in the building running
the Casambi app set as a "gateway" so the cloud can reach the mesh.

Commands:
  login       Authenticate, cache the session, print the network name.
  discover    Fetch and cache the catalog of units, groups and scenes.
  list        Print the cached catalog (names + ids Claude maps against).
  state       Print live on/off + dim level for every unit.
  set         Control one unit:   set "Sanctuary Spot 1" --level 0.4
  group       Control a group:    group "Sanctuary" --level 0.4
  scene       Activate a scene:    scene "Shabbat"
  on / off    Convenience:         off "Lobby"

Add --dry-run to any control command to print the exact message that WOULD be
sent without connecting — useful for validating name resolution before the
API key arrives.
"""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Missing dependency 'requests'. Run: pip install -r requirements.txt")

REST_BASE = "https://door.casambi.com/v1"
WS_URL = "wss://door.casambi.com/v1/bridge/"

HERE = Path(__file__).resolve().parent
SESSION_FILE = HERE / ".casambi_session.json"   # gitignored: holds a session id
CATALOG_FILE = HERE / "devices.json"            # gitignored: building layout


# --------------------------------------------------------------------------- #
# Config / secrets
# --------------------------------------------------------------------------- #
def load_dotenv():
    """Minimal .env loader so we don't need python-dotenv as a dependency."""
    env_path = HERE / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


def get_config():
    load_dotenv()
    api_key = os.environ.get("CASAMBI_API_KEY")
    email = os.environ.get("CASAMBI_EMAIL")
    password = os.environ.get("CASAMBI_PASSWORD")
    network_name = os.environ.get("CASAMBI_NETWORK_NAME")  # optional filter
    missing = [
        name
        for name, val in [
            ("CASAMBI_API_KEY", api_key),
            ("CASAMBI_EMAIL", email),
            ("CASAMBI_PASSWORD", password),
        ]
        if not val
    ]
    if missing:
        sys.exit(
            "Missing required config: "
            + ", ".join(missing)
            + "\nSet them in casambi/.env (copy .env.example) or as env vars."
        )
    return {
        "api_key": api_key,
        "email": email,
        "password": password,
        "network_name": network_name,
    }


# --------------------------------------------------------------------------- #
# REST
# --------------------------------------------------------------------------- #
def rest_headers(api_key, session_id=None):
    h = {"X-Casambi-Key": api_key, "Content-Type": "application/json"}
    if session_id:
        h["X-Casambi-Session"] = session_id
    return h


def create_network_session(cfg):
    """POST /networks/session -> {networkId: {sessionId, name, ...}, ...}."""
    resp = requests.post(
        f"{REST_BASE}/networks/session/",
        headers=rest_headers(cfg["api_key"]),
        json={"email": cfg["email"], "password": cfg["password"]},
        timeout=30,
    )
    if resp.status_code == 401:
        sys.exit("Authentication failed (401). Check CASAMBI_EMAIL / CASAMBI_PASSWORD.")
    if resp.status_code == 403:
        sys.exit("Forbidden (403). Your CASAMBI_API_KEY may be wrong or not yet active.")
    resp.raise_for_status()
    networks = resp.json()
    if not networks:
        sys.exit("No networks returned for these credentials.")

    chosen_id, chosen = None, None
    for net_id, net in networks.items():
        if cfg.get("network_name"):
            if net.get("name", "").lower() == cfg["network_name"].lower():
                chosen_id, chosen = net_id, net
                break
        else:
            chosen_id, chosen = net_id, net
            break
    if chosen is None:
        names = ", ".join(n.get("name", "?") for n in networks.values())
        sys.exit(f"Network '{cfg['network_name']}' not found. Available: {names}")

    return {
        "network_id": chosen.get("id", chosen_id),
        "session_id": chosen["sessionId"],
        "network_name": chosen.get("name", ""),
    }


def load_session(cfg, refresh=False):
    """Return a cached session, creating one if missing/stale/forced."""
    if not refresh and SESSION_FILE.exists():
        try:
            data = json.loads(SESSION_FILE.read_text())
            if data.get("session_id") and data.get("network_id"):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    session = create_network_session(cfg)
    SESSION_FILE.write_text(json.dumps(session, indent=2))
    try:
        SESSION_FILE.chmod(0o600)
    except OSError:
        pass
    return session


def get_network(cfg, session):
    resp = requests.get(
        f"{REST_BASE}/networks/{session['network_id']}/",
        headers=rest_headers(cfg["api_key"], session["session_id"]),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_state(cfg, session):
    resp = requests.get(
        f"{REST_BASE}/networks/{session['network_id']}/state/",
        headers=rest_headers(cfg["api_key"], session["session_id"]),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def build_catalog(network):
    """Reduce a full network document to the name<->id maps we control against."""
    def simplify(collection):
        out = []
        if isinstance(collection, dict):
            items = collection.values()
        else:
            items = collection or []
        for item in items:
            if not isinstance(item, dict):
                continue
            out.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name") or item.get("displayName") or "",
                    "type": item.get("type", ""),
                }
            )
        return out

    return {
        "network_name": network.get("name", ""),
        "units": simplify(network.get("units", {})),
        "groups": simplify(network.get("groups", {})),
        "scenes": simplify(network.get("scenes", {})),
    }


def load_catalog():
    if not CATALOG_FILE.exists():
        sys.exit("No catalog yet. Run:  python casambi_ctrl.py discover")
    return json.loads(CATALOG_FILE.read_text())


def resolve(catalog, kind, target):
    """Resolve a name (case-insensitive, exact then substring) or numeric id."""
    items = catalog.get(kind, [])
    # numeric id
    if str(target).isdigit():
        tid = int(target)
        for it in items:
            if it.get("id") == tid:
                return it
    tl = str(target).lower()
    for it in items:  # exact name
        if (it.get("name") or "").lower() == tl:
            return it
    matches = [it for it in items if tl in (it.get("name") or "").lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(f"{m['name']} (id {m['id']})" for m in matches)
        sys.exit(f"'{target}' is ambiguous in {kind}: {names}. Be more specific or use the id.")
    known = ", ".join(it.get("name", "?") for it in items) or "(none)"
    sys.exit(f"No {kind[:-1]} matching '{target}'. Known {kind}: {known}")


# --------------------------------------------------------------------------- #
# WebSocket control
# --------------------------------------------------------------------------- #
def build_target_controls(level=None, kelvin=None):
    tc = {}
    if level is not None:
        tc["Dimmer"] = {"value": max(0.0, min(1.0, float(level)))}
    if kelvin is not None:
        tc["ColorTemperature"] = {"value": int(kelvin)}
        tc["Colorsource"] = {"source": "TW"}
    return tc


def send_ws(cfg, session, control_msg, dry_run=False):
    """Open the socket, send OPEN then the control message, print acks."""
    wire = 1
    open_msg = {
        "method": "open",
        "id": session["network_id"],
        "session": session["session_id"],
        "ref": str(uuid.uuid4()),
        "wire": wire,
        "type": 1,
    }
    control_msg = {"wire": wire, **control_msg}

    if dry_run:
        print("DRY RUN — would connect to", WS_URL)
        print("OPEN    :", json.dumps(open_msg))
        print("CONTROL :", json.dumps(control_msg))
        return

    try:
        import websocket  # websocket-client
    except ImportError:
        sys.exit("Missing dependency 'websocket-client'. Run: pip install -r requirements.txt")

    ws = websocket.create_connection(
        WS_URL, subprotocols=[cfg["api_key"]], timeout=15
    )
    try:
        ws.send(json.dumps(open_msg))
        opened = json.loads(ws.recv())
        if opened.get("wireStatus") not in (None, "open", "openWireSucceed"):
            print("Warning: unexpected open response:", opened, file=sys.stderr)
        ws.send(json.dumps(control_msg))
        # brief drain for an ack / state echo
        ws.settimeout(3)
        try:
            print("Response:", ws.recv())
        except Exception:
            print("Sent (no ack within timeout — usually fine).")
    finally:
        try:
            ws.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_login(args):
    cfg = get_config()
    session = load_session(cfg, refresh=True)
    print(f"Logged in to network '{session['network_name']}' (id {session['network_id']}).")
    print(f"Session cached in {SESSION_FILE.name}. Next: python casambi_ctrl.py discover")


def cmd_discover(args):
    cfg = get_config()
    session = load_session(cfg)
    network = get_network(cfg, session)
    catalog = build_catalog(network)
    CATALOG_FILE.write_text(json.dumps(catalog, indent=2))
    print(f"Network: {catalog['network_name']}")
    for kind in ("units", "groups", "scenes"):
        print(f"\n{kind.upper()} ({len(catalog[kind])}):")
        for it in catalog[kind]:
            print(f"  [{it['id']}] {it['name']}")
    print(f"\nCatalog written to {CATALOG_FILE.name}.")


def cmd_list(args):
    catalog = load_catalog()
    print(json.dumps(catalog, indent=2))


def cmd_state(args):
    cfg = get_config()
    session = load_session(cfg)
    state = get_state(cfg, session)
    units = state.get("units", state)
    if isinstance(units, dict):
        units = units.values()
    for u in units:
        if not isinstance(u, dict):
            continue
        on = u.get("on")
        dim = u.get("dimLevel", u.get("controls", {}))
        print(f"  [{u.get('id')}] {u.get('name','?'):<28} on={on} dim={dim}")


def _dispatch(args, msg, label):
    """Print what we're doing, then send (or dry-run without needing secrets)."""
    print(label)
    if args.dry_run:
        send_ws({"api_key": "?"}, {"network_id": "?", "session_id": "?"}, msg, dry_run=True)
        return
    cfg = get_config()
    session = load_session(cfg)
    send_ws(cfg, session, msg, dry_run=False)


def _control_unit(args, level=None, kelvin=None):
    catalog = load_catalog()
    unit = resolve(catalog, "units", args.target)
    tc = build_target_controls(level, kelvin)
    msg = {"method": "controlUnit", "id": unit["id"], "targetControls": tc}
    _dispatch(args, msg, f"Unit '{unit['name']}' (id {unit['id']}) -> {tc}")


def cmd_set(args):
    _control_unit(args, level=args.level, kelvin=args.kelvin)


def cmd_on(args):
    _control_unit(args, level=1.0)


def cmd_off(args):
    _control_unit(args, level=0.0)


def cmd_group(args):
    catalog = load_catalog()
    group = resolve(catalog, "groups", args.target)
    tc = build_target_controls(level=args.level, kelvin=args.kelvin)
    msg = {"method": "controlGroup", "id": group["id"], "targetControls": tc}
    _dispatch(args, msg, f"Group '{group['name']}' (id {group['id']}) -> {tc}")


def cmd_scene(args):
    # NOTE: verify the scene message against your live network the first time —
    # some networks expect controlScene with `level`, others a targetControls map.
    catalog = load_catalog()
    scene = resolve(catalog, "scenes", args.target)
    level = 1.0 if args.level is None else args.level
    msg = {"method": "controlScene", "id": scene["id"], "level": level}
    _dispatch(args, msg, f"Scene '{scene['name']}' (id {scene['id']}) -> level {level}")


# --------------------------------------------------------------------------- #
# Argparse
# --------------------------------------------------------------------------- #
def build_parser():
    p = argparse.ArgumentParser(description="Casambi lighting control CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="authenticate and cache a session").set_defaults(func=cmd_login)
    sub.add_parser("discover", help="fetch/cache the catalog").set_defaults(func=cmd_discover)
    sub.add_parser("list", help="print the cached catalog").set_defaults(func=cmd_list)
    sub.add_parser("state", help="print live unit state").set_defaults(func=cmd_state)

    def add_control_args(sp, with_level=True, with_kelvin=True):
        sp.add_argument("target", help="unit/group/scene name (or numeric id)")
        if with_level:
            sp.add_argument("--level", type=float, default=None,
                            help="0.0-1.0 dim level")
        if with_kelvin:
            sp.add_argument("--kelvin", type=int, default=None,
                            help="color temperature in Kelvin (tunable-white fixtures)")
        sp.add_argument("--dry-run", action="store_true",
                        help="print the message without connecting")

    sp = sub.add_parser("set", help="control one unit"); add_control_args(sp)
    sp.set_defaults(func=cmd_set)
    sp = sub.add_parser("on", help="turn a unit fully on"); add_control_args(sp, with_level=False)
    sp.set_defaults(func=cmd_on)
    sp = sub.add_parser("off", help="turn a unit off"); add_control_args(sp, with_level=False)
    sp.set_defaults(func=cmd_off)
    sp = sub.add_parser("group", help="control a group"); add_control_args(sp)
    sp.set_defaults(func=cmd_group)
    sp = sub.add_parser("scene", help="activate a scene"); add_control_args(sp, with_kelvin=False)
    sp.set_defaults(func=cmd_scene)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
