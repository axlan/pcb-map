from pathlib import Path
import sqlite3
import shutil
import os
import sys
import tempfile

# https://github.com/costastf/locationsharinglib
from locationsharinglib import Person, Service

sys.path.insert(0, str(Path(__file__).parents[1]))

from pcb_map.constants import (
    CACHE_DIR,
)

COOKIES_FILE = os.path.join(CACHE_DIR, "google_cookies.txt")


# ─── Cookie Loaders ─────────────────────────────────────────────


def _find_firefox_profile():
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support/Firefox/Profiles/")
    elif sys.platform.startswith("linux"):
        base = os.path.expanduser("~/.mozilla/firefox/")
        if not os.path.exists(base):
            base = os.path.expanduser("~/snap/firefox/common/.mozilla/firefox/")
    elif sys.platform == "win32":
        base = os.path.expanduser("~/AppData/Roaming/Mozilla/Firefox/Profiles/")
    else:
        raise OSError(f"Unsupported platform: {sys.platform}")

    profiles = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]

    # Prefer default-release, then default, then first found
    for preferred in ["default-release", "default"]:
        match = next((p for p in profiles if preferred in p), None)
        if match:
            return os.path.join(base, match)

    if profiles:
        return os.path.join(base, profiles[0])

    raise FileNotFoundError(f"No Firefox profiles found in {base}")


def get_firefox_location_cookie():
    profile = _find_firefox_profile()
    print(f"Using Firefox profile: {profile}")

    cookies_db = os.path.join(profile, "cookies.sqlite")
    if not os.path.exists(cookies_db):
        raise FileNotFoundError(f"cookies.sqlite not found in {profile}")

    # Create a temporary file that's automatically deleted when context exits
    with tempfile.NamedTemporaryFile(suffix=".sqlite") as tmp_file:
        tmp_db = tmp_file.name
        shutil.copy2(cookies_db, tmp_db)
        print("Copied cookies database (safe to run with Firefox open)")

        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT host, path, isSecure, expiry, name, value
            FROM moz_cookies
            WHERE host LIKE '%google.com%'
        """)

        rows = cursor.fetchall()
        conn.close()

    if not rows:
        raise ValueError(
            "No Google cookies found — are you logged into Google in Firefox?"
        )

    CACHE_DIR.mkdir(exist_ok=True)
    with open(COOKIES_FILE, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for host, path, secure, expiry, name, value in rows:
            # Netscape format columns:
            # domain  include_subdomains  path  secure  expiry  name  value
            include_subdomains = "TRUE" if host.startswith(".") else "FALSE"
            secure_str = "TRUE" if secure else "FALSE"
            f.write(
                f"{host}\t{include_subdomains}\t{path}\t{secure_str}\t{expiry}\t{name}\t{value}\n"
            )

    print(f"Exported {len(rows)} Google cookies to {COOKIES_FILE}")


# ─── FETCH SHARED LOCATIONS ───────────────────────────────────────────


def fetch_locations(cookies_file, email) -> list[Person]:
    print(f"\nConnecting to Google Location Sharing as {email}...")
    service = Service(cookies_file=cookies_file, authenticating_account=email)

    people = list(service.get_all_people())
    if not people:
        print("No one is currently sharing their location with you.")
        return []

    return people


# ─── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        # Only extract cookies if they don't already exist
        if not os.path.exists(COOKIES_FILE):
            print(f"Cookies not found at {COOKIES_FILE}, extracting from Firefox...")
            get_firefox_location_cookie()
        else:
            print(f"Using existing cookies from {COOKIES_FILE}")

        people = fetch_locations(COOKIES_FILE, "me")

        print(f"\nFound {len(people)} people sharing location:\n")
        for person in people:
            print(f"  Name:      {person.full_name}")
            print(f"  Latitude:  {person.latitude}")
            print(f"  Longitude: {person.longitude}")
            print(f"  Address:   {person.address}")
            print(f"  Last seen: {person.datetime}")
            print()
    except FileNotFoundError as e:
        print(f"[Error] {e}")
    except ValueError as e:
        print(f"[Error] {e}")
    except Exception as e:
        print(f"[Unexpected error] {e}")
