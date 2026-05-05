import sqlite3
import shutil
import os
import sys
import tempfile
# https://github.com/costastf/locationsharinglib
from locationsharinglib import Service


COOKIES_FILE_NAME = os.path.join(COOKIES_DIR, "google_cookies.txt")

# ─── STEP 1: FIND FIREFOX PROFILE ─────────────────────────────────────────────

def find_firefox_profile():
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

# ─── STEP 2: EXPORT GOOGLE COOKIES FROM FIREFOX ───────────────────────────────

def export_google_cookies(output_path):
    profile = find_firefox_profile()
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
        raise ValueError("No Google cookies found — are you logged into Google in Firefox?")

    with open(output_path, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for host, path, secure, expiry, name, value in rows:
            # Netscape format columns:
            # domain  include_subdomains  path  secure  expiry  name  value
            include_subdomains = "TRUE" if host.startswith(".") else "FALSE"
            secure_str = "TRUE" if secure else "FALSE"
            f.write(f"{host}\t{include_subdomains}\t{path}\t{secure_str}\t{expiry}\t{name}\t{value}\n")

    print(f"Exported {len(rows)} Google cookies to {output_path}")
    return output_path

# ─── STEP 3: FETCH SHARED LOCATIONS ───────────────────────────────────────────

def fetch_locations(cookies_file, email):
    print(f"\nConnecting to Google Location Sharing as {email}...")
    service = Service(cookies_file=cookies_file, authenticating_account=email)

    people = list(service.get_all_people())
    if not people:
        print("No one is currently sharing their location with you.")
        return

    print(f"\nFound {len(people)} people sharing location:\n")
    for person in people:
        print(f"  Name:      {person.full_name}")
        print(f"  Latitude:  {person.latitude}")
        print(f"  Longitude: {person.longitude}")
        print(f"  Address:   {person.address}")
        print(f"  Last seen: {person.datetime}")
        print()

# ─── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        # Create cookies directory if it doesn't exist
        os.makedirs(COOKIES_DIR, exist_ok=True)

        # Only extract cookies if they don't already exist
        if not os.path.exists(COOKIES_FILE):
            print(f"Cookies not found at {COOKIES_FILE}, extracting from Firefox...")
            export_google_cookies(COOKIES_FILE)
        else:
            print(f"Using existing cookies from {COOKIES_FILE}")

        fetch_locations(COOKIES_FILE, YOUR_EMAIL)
    except FileNotFoundError as e:
        print(f"[Error] {e}")
    except ValueError as e:
        print(f"[Error] {e}")
    except Exception as e:
        print(f"[Unexpected error] {e}")
