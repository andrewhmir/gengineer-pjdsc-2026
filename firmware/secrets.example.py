# !!!! Request to DELETE this since we will not be using CircuitPython for this project

# Template for the credentials file the board uses. Committed; placeholders only.
#
# CircuitPython expects a module named secrets.py beside code.py at the root of
# the CIRCUITPY drive. This file is the committed template for it:
#
#   cp firmware/secrets.example.py /path/to/CIRCUITPY/secrets.py
#
# The real secrets.py is gitignored (see firmware/.gitignore and the root
# .gitignore) and must never be committed. Replace every placeholder locally, on
# the board copy only, and never paste a real value back into this file. CI's
# `secrets` job scans with gitleaks and allowlists this path precisely because it
# is a placeholder template (see .gitleaks.toml), so adding a real value here also
# defeats the scanner. See SECURITY.md for what to do if one is ever committed.
#
# Keep the keys below in the same spelling the firmware reads: CircuitPython
# imports this module and uses these names directly, so a renamed key is a silent
# failure to authenticate rather than an error.
#
# No firmware code reads these values yet, because no network code exists yet.

"""Committed placeholder template for the board's gitignored secrets.py."""

# --- WiFi ---------------------------------------------------------------------------
# Credentials of the network the node joins to post readings.
# Two-letter country code of the network's regulatory domain, if set. Leave blank
# when it does not apply.
WIFI_COUNTRY = ""

# Network name (SSID). Case-sensitive and must match exactly.
WIFI_SSID = "YOUR_WIFI_SSID"

# Network passphrase. Placeholder only; the real value lives on the board.
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"

# --- Sensor node API ----------------------------------------------------------------
# Shared token the node presents when posting a reading. Generate a fresh one per
# deployment rather than reusing this placeholder:
#   uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
SENSOR_API_TOKEN = "YOUR_SENSOR_API_TOKEN"

# Base URL of the endpoint that accepts readings. No trailing slash.
SENSOR_API_BASE_URL = "https://YOUR_ENDPOINT_HOST/api/v1"
