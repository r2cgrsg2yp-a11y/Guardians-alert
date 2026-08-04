#!/usr/bin/env python3
import json, os, time, urllib.request

API = "https://api.themeparks.wiki/v1"
PARK_NAME = "EPCOT"
RIDE_MATCH = "cosmic rewind"
THRESHOLD = int(os.environ.get("THRESHOLD", "40"))
NTFY_TOPIC = os.environ["NTFY_TOPIC"]
INTERVAL = 300
RUN_MINUTES = 330

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "guardians-alert/2.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def find_park_id():
    for dest in get(f"{API}/destinations").get("destinations", []):
        for park in dest.get("parks", []):
            if park.get("name", "").upper() == PARK_NAME.upper():
                return park["id"]
    raise SystemExit("Park not found")

def current_wait(park_id):
    for e in get(f"{API}/entity/{park_id}/live").get("liveData", []):
        if RIDE_MATCH in e.get("name", "").lower():
            if e.get("status") != "OPERATING":
                return None
            return ((e.get("queue") or {}).get("STANDBY") or {}).get("waitTime")
    return None

def notify(wait):
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=f"Guardians is under {THRESHOLD} minutes - {wait} min right now".encode(),
        headers={"Title": "Cosmic Rewind", "Priority": "high", "Tags": "rocket"},
    )
    urllib.request.urlopen(req, timeout=20).read()

park_id = find_park_id()
deadline = time.time() + RUN_MINUTES * 60
was_below = False

while time.time() < deadline:
    try:
        wait = current_wait(park_id)
        if wait is None:
            print("closed / no standby data", flush=True)
            was_below = False
        else:
            is_below = wait < THRESHOLD
            print(f"wait={wait} below={is_below} was_below={was_below}", flush=True)
            if is_below and not was_below:
                notify(wait)
                print("notified", flush=True)
            was_below = is_below
    except Exception as e:
        print(f"error: {e}", flush=True)
    time.sleep(INTERVAL)
