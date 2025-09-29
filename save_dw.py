import os, re
from datetime import datetime, timezone
import requests
import spotipy
from spotipy.exceptions import SpotifyException

def get_access_token(client_id, client_secret, refresh_token):
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=(client_id, client_secret),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

def spotify_client():
    token = get_access_token(
        os.environ["SPOTIFY_CLIENT_ID"],
        os.environ["SPOTIFY_CLIENT_SECRET"],
        os.environ["SPOTIFY_REFRESH_TOKEN"],
    )
    return spotipy.Spotify(auth=token)

def normalize_playlist_id(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if re.fullmatch(r"[A-Za-z0-9]{22}", raw):
        return raw
    m = re.search(r"spotify:playlist:([A-Za-z0-9]{22})", raw)
    if m: return m.group(1)
    m = re.search(r"/playlist/([A-Za-z0-9]{22})", raw)
    if m: return m.group(1)
    raise ValueError("DW_PLAYLIST_ID is not a valid ID/URL")

def find_dw_playlist_id(sp):
    raw = os.environ.get("DW_PLAYLIST_ID", "")
    if raw:
        return normalize_playlist_id(raw)

    # Fallback: try to locate by name + owner
    results = sp.current_user_playlists(limit=50)
    while True:
        for pl in results["items"]:
            name = (pl.get("name") or "").lower()
            owner = (pl.get("owner", {}).get("id") or "").lower()
            if name == "discover weekly" and owner == "spotify":
                return pl["id"]
        if results.get("next"):
            results = sp.next(results)
        else:
            break
    raise RuntimeError(
        "Couldn't find 'Discover Weekly' in your playlists. "
        "Set DW_PLAYLIST_ID as a secret with the raw ID or full link."
    )

def fetch_tracks(sp, playlist_id):
    uris = []
    results = sp.playlist_items(
        playlist_id,
        fields="items(track(uri,is_local)),next",
        additional_types=["track"],
    )
    while True:
        for item in results["items"]:
            t = item.get("track")
            if t and not t.get("is_local") and t.get("uri"):
                uris.append(t["uri"])
        if results.get("next"):
            results = sp.next(results)
        else:
            break
    return uris

def create_new_weekly_playlist(sp, base="Discover Weekly"):
    me = sp.me()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    name = f"{base} – {date_str}"
    desc = "Auto-archived from Discover Weekly via GitHub Actions."
    pl = sp.user_playlist_create(user=me["id"], name=name, public=False, description=desc)
    return pl["id"]

def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]

def main():
    sp = spotify_client()
    try:
        dw_id = find_dw_playlist_id(sp)
    except Exception as e:
        raise SystemExit(f"[setup] {e}")

    try:
        tracks = fetch_tracks(sp, dw_id)
    except SpotifyException as e:
        # Clearer hints for 403/404 on algorithmic playlists
        if e.http_status in (403, 404):
            raise SystemExit(
                f"[access] Spotify API denied access to Discover Weekly (HTTP {e.http_status}). "
                "This often happens with newer developer apps. "
                "Workarounds: set DW_PLAYLIST_ID to your exact DW link/ID, or use a pre-approved service."
            )
        raise

    if not tracks:
        print("[info] No tracks found; exiting.")
        return

    new_pl = create_new_weekly_playlist(sp)
    for batch in chunked(tracks, 100):
        sp.playlist_add_items(new_pl, batch)
    print(f"[done] Saved {len(tracks)} tracks into a new playlist.")

if __name__ == "__main__":
    main()
