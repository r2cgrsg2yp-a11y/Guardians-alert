#!/usr/bin/env python3
"""
Checks the live standby wait for Guardians of the Galaxy: Cosmic Rewind
and pushes an iPhone notification via ntfy when it drops below THRESHOLD.

Only fires on a *crossing* (was above, now below) so you don't get spammed
every 5 minutes while the wait sits at 30.
"""

import json
import os
import pathlib
import sys
import urllib.request

API = "https://api.themeparks.wiki/v1"
PARK_NAME = "EPCOT"
RIDE_MATCH = "cosmic rewind"          # lowercase substring match on ride name
THRESHOLD = int(os.environ.get("THRESHOLD", "40"))
NTFY_TOPIC = os.environ["NTFY_TOPIC"]  # set as a GitHub secret
STATE_FILE = pathlib.Path("state.json")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "guardians-alert/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def find_park_id():
    """Resolve EPCOT's entity ID at runtime so nothing is hardcoded/stale."""
    data = get(f"{API}/destinations")
    for dest in data.get("destinations", []):
        for park in dest.get("parks", []):
            if park.get("name", "").upper() == PARK_NAME.upper():
                return park["id"]
    raise SystemExit(f"Could not find park: {PARK_NAME}")


def current_wait(park_id):
    """Return standby wait in minutes, or None if the ride is closed/unlisted."""
    data = get(f"{API}/entity/{park_id}/live")
    for entry in data.get("liveData", []):
        if RIDE_MATCH in entry.get("name", "").lower():
            if entry.get("status") != "OPERATING":
                return None
            standby = (entry.get("queue") or {}).get("STANDBY") or {}
            return standby.get("waitTime")
    return None


def notify(wait):
    body = f"Guardians is under {THRESHOLD} minutes — {wait} min right now".encode()
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=body,
        headers={
            "Title": "Cosmic Rewind",
            "Priority": "high",
            "Tags": "rocket",
        },
    )
    urllib.request.urlopen(req, timeout=20).read()


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text()).get("below", False)
        except Exception:
            pass
    return False


def save_state(below):
    STATE_FILE.write_text(json.dumps({"below": below}))


def main():
    wait = current_wait(find_park_id())
    was_below = load_state()

    if wait is None:
        print("Ride closed or no standby data — skipping.")
        save_state(False)   # reset so it can fire again when it reopens
        return

    is_below = wait < THRESHOLD
    print(f"Wait: {wait} min | below={is_below} | was_below={was_below}")

    if is_below and not was_below:
        notify(wait)
        print("Notification sent.")

    save_state(is_below)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
