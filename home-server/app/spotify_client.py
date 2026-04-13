"""Spotify API client for Ear AI."""

from __future__ import annotations

from typing import Optional
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from .config import settings


class SpotifyClient:
    """Manages Spotify API interactions."""

    def __init__(self) -> None:
        if not settings.spotify_client_id or not settings.spotify_client_secret:
            raise ValueError(
                "Spotify credentials not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env"
            )
        
        # Use Client Credentials flow for server-to-server authentication
        # This doesn't require user login for basic operations
        auth_manager = SpotifyClientCredentials(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
        )
        self.client = spotipy.Spotify(auth_manager=auth_manager)
    
    def search_track(self, query: str) -> Optional[dict]:
        """Search for a track and return the first result."""
        try:
            results = self.client.search(q=query, type="track", limit=1)
            tracks = results.get("tracks", {}).get("items", [])
            if tracks:
                track = tracks[0]
                return {
                    "id": track["id"],
                    "name": track["name"],
                    "artist": track["artists"][0]["name"] if track["artists"] else "Unknown",
                    "uri": track["uri"],
                    "url": track["external_urls"].get("spotify", ""),
                }
            return None
        except Exception as e:
            return {"error": str(e)}
    
    def search_playlist(self, query: str) -> Optional[dict]:
        """Search for a playlist and return the first result."""
        try:
            results = self.client.search(q=query, type="playlist", limit=1)
            playlists = results.get("playlists", {}).get("items", [])
            if playlists:
                playlist = playlists[0]
                return {
                    "id": playlist["id"],
                    "name": playlist["name"],
                    "uri": playlist["uri"],
                    "url": playlist["external_urls"].get("spotify", ""),
                    "track_count": playlist["tracks"]["total"],
                }
            return None
        except Exception as e:
            return {"error": str(e)}
    
    def get_featured_playlists(self) -> list[dict]:
        """Get currently featured playlists."""
        try:
            results = self.client.featured_playlists(limit=5)
            playlists = []
            for playlist in results.get("playlists", {}).get("items", []):
                playlists.append({
                    "id": playlist["id"],
                    "name": playlist["name"],
                    "uri": playlist["uri"],
                    "url": playlist["external_urls"].get("spotify", ""),
                })
            return playlists
        except Exception as e:
            return [{"error": str(e)}]
    
    def get_new_releases(self) -> list[dict]:
        """Get new releases."""
        try:
            results = self.client.new_releases(limit=5)
            albums = []
            for album in results.get("albums", {}).get("items", []):
                albums.append({
                    "id": album["id"],
                    "name": album["name"],
                    "artist": album["artists"][0]["name"] if album["artists"] else "Unknown",
                    "uri": album["uri"],
                    "url": album["external_urls"].get("spotify", ""),
                })
            return albums
        except Exception as e:
            return [{"error": str(e)}]
    
    def get_recommendations(self, seed_tracks: list[str] = None, seed_genres: list[str] = None) -> list[dict]:
        """Get recommendations based on seeds."""
        try:
            results = self.client.recommendations(
                seed_tracks=seed_tracks or [],
                seed_genres=seed_genres or ["pop"],
                limit=10
            )
            tracks = []
            for track in results.get("tracks", []):
                tracks.append({
                    "id": track["id"],
                    "name": track["name"],
                    "artist": track["artists"][0]["name"] if track["artists"] else "Unknown",
                    "uri": track["uri"],
                    "url": track["external_urls"].get("spotify", ""),
                })
            return tracks
        except Exception as e:
            return [{"error": str(e)}]
    
    def get_user_top_tracks(self, time_range: str = "short_term") -> list[dict]:
        """Get user's top tracks (requires user OAuth - not available with Client Credentials)."""
        return [{"error": "User top tracks requires Spotify authentication from the mobile app"}]
    
    def format_for_playback(self, item: dict) -> dict:
        """Format a Spotify item (track/playlist) for playback on mobile app."""
        return {
            "uri": item.get("uri", ""),
            "name": item.get("name", ""),
            "artist": item.get("artist", ""),
            "url": item.get("url", ""),
            "id": item.get("id", ""),
        }


# Global Spotify client instance
_spotify_instance: Optional[SpotifyClient] = None


def get_spotify_client() -> Optional[SpotifyClient]:
    """Get or create the global Spotify client instance."""
    global _spotify_instance
    if _spotify_instance is None:
        try:
            _spotify_instance = SpotifyClient()
        except ValueError:
            # Spotify not configured
            return None
    return _spotify_instance
