import os
from datetime import datetime, timezone
import requests
import spotipy

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

def find_dw_playlist_id(sp):
    pid = os.environ.get("DW_PLAYLIST_ID")
    if pid:
        return pid
    results = sp.current_user_playlists(limit=50)
    while results:
        for pl in results["items"]:
            name = (pl["name"] or "").lower()
            owner = (pl["owner"]["id"] or "").lower()
            if name == "discover weekly" and owner == "spotify":
                return pl["id"]
        if results["next"]:
            results = sp.next(results)
        else:
            break
    raise RuntimeError("Couldn’t find 'Discover Weekly'. Set DW_PLAYLIST_ID as a secret.")

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
    dw_id = find_dw_playlist_id(sp)
    tracks = fetch_tracks(sp, dw_id)
    if not tracks:
        print("No tracks found, exiting.")
        return
    new_pl = create_new_weekly_playlist(sp)
    for batch in chunked(tracks, 100):
        sp.playlist_add_items(new_pl, batch)
    print(f"Saved {len(tracks)} tracks into a new playlist.")

if __name__ == "__main__":
    main()
