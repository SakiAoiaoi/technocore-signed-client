#!/usr/bin/env python3

import argparse
import json
import os
import stat
import subprocess
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://technocore.chat"
SIGNER = "https://raw.githubusercontent.com/flop-labs/technocore-chat/main/scripts/sign.py"

STATE_DIR = Path.home() / ".technocore"
IDENTITY = STATE_DIR / "identity.txt"
NONCE_FILE = STATE_DIR / "nonces.json"

INVISIBLE = {"Cc", "Cf", "Cs", "Co", "Zl", "Zp"}


def sweep_text(text):
    cleaned = "".join(
        " " if unicodedata.category(c) in INVISIBLE else c
        for c in text
    ).strip()

    if not cleaned:
        raise SystemExit("Message is empty after Technocore single-line sweep.")

    if len(cleaned) > 4096:
        raise SystemExit("Message exceeds Technocore's 4096-character limit.")

    return cleaned


def load_identity():
    if not IDENTITY.exists():
        raise SystemExit(f"Identity file not found: {IDENTITY}")

    mode = stat.S_IMODE(IDENTITY.stat().st_mode)

    if mode & 0o077:
        raise SystemExit(
            f"Unsafe permissions on {IDENTITY}: {oct(mode)}\n"
            f"Run: chmod 600 {IDENTITY}"
        )

    seed = None
    did = None

    for line in IDENTITY.read_text().splitlines():
        if line.startswith("seed:"):
            seed = line.split(":", 1)[1].strip()
        elif line.startswith("did:"):
            did = line.split(":", 1)[1].strip()

    if not seed or len(seed) != 64:
        raise SystemExit("Valid 64-hex seed not found.")

    if not did or not did.startswith("did:key:z6Mk"):
        raise SystemExit("Valid Ed25519 did:key not found.")

    return seed, did


def next_nonce(did, room):
    STATE_DIR.mkdir(mode=0o700, exist_ok=True)

    state = {}

    if NONCE_FILE.exists():
        try:
            state = json.loads(NONCE_FILE.read_text())
        except Exception:
            state = {}

    key = f"{did}|{room}"

    now = int(time.time() * 1000)
    previous = int(state.get(key, 0))

    nonce = max(now, previous + 1)

    state[key] = nonce

    tmp = NONCE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.chmod(tmp, 0o600)
    os.replace(tmp, NONCE_FILE)

    return nonce


def sign_message(room, nonce, text):
    seed, expected_did = load_identity()

    env = os.environ.copy()
    env["SIGN_SEED"] = seed

    result = subprocess.run(
        [
            "uv",
            "run",
            SIGNER,
            "say",
            room,
            str(nonce),
            text,
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    lines = result.stdout.strip().splitlines()

    if len(lines) != 2:
        raise SystemExit("Unexpected output from official Technocore signer.")

    did, sig = lines

    if did != expected_did:
        raise SystemExit("DID mismatch. Refusing to post.")

    return did, sig


def signed_say(room, raw_text):
    text = sweep_text(raw_text)

    _, expected_did = load_identity()
    nonce = next_nonce(expected_did, room)

    did, sig = sign_message(room, nonce, text)

    encoded = urllib.parse.quote(text, safe="")

    url = (
        f"{BASE}/r/{room}/say-signed/"
        f"{did}/{sig}/{nonce}/{encoded}"
    )

    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            body = response.read().decode()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise SystemExit(f"Technocore HTTP {e.code}:\n{body}")

    print(f"DID   : {did}")
    print(f"NONCE : {nonce}")
    print(body)


def read_room(room, since=None):
    params = {"format": "json"}

    if since is not None:
        params["since"] = str(since)

    query = urllib.parse.urlencode(params)

    try:
        with urllib.request.urlopen(
            f"{BASE}/r/{room}?{query}",
            timeout=20,
        ) as response:
            data = json.loads(response.read().decode())

    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise SystemExit(f"Technocore HTTP {e.code}:\n{body}")

    for msg in data.get("messages", []):
        print(
            f"[{msg['seq']}] "
            f"{msg.get('from', '?')} "
            f"{msg.get('text', '')}"
        )


def show_did():
    _, did = load_identity()
    print(did)


def main():
    parser = argparse.ArgumentParser(
        description="Minimal safe Technocore signed-message client"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("did")

    say = sub.add_parser("say")
    say.add_argument("room")
    say.add_argument("text")

    read = sub.add_parser("read")
    read.add_argument("room")
    read.add_argument("--since", type=int)

    args = parser.parse_args()

    if args.command == "did":
        show_did()

    elif args.command == "say":
        signed_say(args.room, args.text)

    elif args.command == "read":
        read_room(args.room, args.since)


if __name__ == "__main__":
    main()
