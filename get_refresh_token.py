# get_refresh_token.py — no local server required
import urllib.parse
import requests
from urllib.parse import urlparse, parse_qs

CLIENT_ID = "21463291771945baa4cafa68f678c27d"
CLIENT_SECRET = "6338e5bffd47452f97062c94e049ebec"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPE = "playlist-read-private playlist-modify-private playlist-modify-public playlist-read-collaborative"

params = {
    "client_id": CLIENT_ID,
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPE,
}
auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)
print("\nOpen this URL, log in, approve:\n" + auth_url)

redirected = input("\nPaste the FULL redirect URL you land on: ").strip()
parsed = urlparse(redirected)
qs = parse_qs(parsed.query)
if "code" not in qs:
    raise SystemExit("No ?code= in the URL. Paste the entire address bar value.")
code = qs["code"][0]

token_resp = requests.post(
    "https://accounts.spotify.com/api/token",
    data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
    auth=(CLIENT_ID, CLIENT_SECRET),
    timeout=30,
)
if token_resp.status_code != 200:
    raise SystemExit(f"Token exchange failed: {token_resp.status_code} {token_resp.text}")

data = token_resp.json()
refresh_token = data.get("refresh_token")
if not refresh_token:
    raise SystemExit("No refresh_token returned (did you approve all scopes?).")
print("\nREFRESH_TOKEN=", refresh_token)
