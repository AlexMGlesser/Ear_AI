"""Music player state management for Ear AI.

The server manages the music library and playback state.
The mobile app handles actual audio playback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Song:
    """Represents a song file."""
    path: str
    filename: str


@dataclass
class PlayerState:
    """Current state of the music player on the mobile app."""
    is_playing: bool = False
    is_paused: bool = False
    current_song: Optional[Song] = None
    current_position_ms: int = 0  # in milliseconds
    volume: float = 1.0  # 0.0 to 1.0


class MusicPlayer:
    """Manages music library and playback state for the mobile app."""
    
    SUPPORTED_FORMATS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac"}
    
    def __init__(self, music_folder: str = "E:\\Music") -> None:
        self.music_folder = Path(music_folder)
        self.state = PlayerState()
        self.playlist: list[Song] = []
        self.playlist_index = 0
        self._load_playlist()
    
    def _load_playlist(self) -> None:
        """Scan music folder and load all supported audio files."""
        self.playlist = []
        
        if not self.music_folder.exists():
            return
        
        for file_path in sorted(self.music_folder.rglob("*")):
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                song = Song(
                    path=str(file_path),
                    filename=file_path.name
                )
                self.playlist.append(song)
    
    def get_playlist(self) -> list[dict]:
        """Return list of all available songs."""
        return [
            {
                "index": i,
                "filename": song.filename,
                "path": song.path,
            }
            for i, song in enumerate(self.playlist)
        ]
    
    def play(self, song_index: Optional[int] = None) -> dict:
        """Start playing a song."""
        if not self.playlist:
            return {"ok": False, "message": "No songs in playlist"}
        
        if song_index is not None:
            if 0 <= song_index < len(self.playlist):
                self.playlist_index = song_index
            else:
                return {"ok": False, "message": f"Invalid song index: {song_index}"}
        
        song = self.playlist[self.playlist_index]
        self.state.is_playing = True
        self.state.is_paused = False
        self.state.current_song = song
        self.state.current_position_ms = 0
        
        return {
            "ok": True,
            "message": f"Playing: {song.filename}",
            "song": song.filename,
            "index": self.playlist_index,
        }
    
    def play_random(self) -> dict:
        """Play a random song from the playlist."""
        if not self.playlist:
            return {"ok": False, "message": "No songs in playlist"}
        
        import random
        self.playlist_index = random.randint(0, len(self.playlist) - 1)
        return self.play()
    
    def pause(self) -> dict:
        """Pause the currently playing song."""
        if not self.state.is_playing:
            return {"ok": False, "message": "No song is playing"}
        
        self.state.is_paused = True
        self.state.is_playing = False
        return {"ok": True, "message": "Music paused"}
    
    def resume(self) -> dict:
        """Resume the paused song."""
        if not self.state.is_paused:
            return {"ok": False, "message": "No paused song to resume"}
        
        self.state.is_paused = False
        self.state.is_playing = True
        return {"ok": True, "message": "Music resumed"}
    
    def stop(self) -> dict:
        """Stop the currently playing song."""
        if not self.state.is_playing and not self.state.is_paused:
            return {"ok": False, "message": "No song is playing"}
        
        self.state.is_playing = False
        self.state.is_paused = False
        self.state.current_song = None
        self.state.current_position_ms = 0
        return {"ok": True, "message": "Music stopped"}
    
    def next_song(self) -> dict:
        """Skip to next song in playlist."""
        if not self.playlist:
            return {"ok": False, "message": "No songs in playlist"}
        
        self.playlist_index = (self.playlist_index + 1) % len(self.playlist)
        return self.play()
    
    def previous_song(self) -> dict:
        """Go back to previous song in playlist."""
        if not self.playlist:
            return {"ok": False, "message": "No songs in playlist"}
        
        self.playlist_index = (self.playlist_index - 1) % len(self.playlist)
        return self.play()
    
    def set_volume(self, volume: float) -> dict:
        """Set volume (0.0 to 1.0)."""
        volume = max(0.0, min(1.0, volume))
        self.state.volume = volume
        return {"ok": True, "message": f"Volume set to {volume * 100:.0f}%", "volume": volume}
    
    def get_status(self) -> dict:
        """Get current player status."""
        current = None
        if self.state.current_song:
            current = {
                "filename": self.state.current_song.filename,
                "path": self.state.current_song.path,
            }
        
        return {
            "is_playing": self.state.is_playing,
            "is_paused": self.state.is_paused,
            "current_song": current,
            "current_position_ms": self.state.current_position_ms,
            "volume": self.state.volume,
            "playlist_size": len(self.playlist),
            "current_index": self.playlist_index if self.state.current_song else -1,
        }


# Global player instance
_player_instance: Optional[MusicPlayer] = None


def get_music_player() -> MusicPlayer:
    """Get or create the global music player instance."""
    global _player_instance
    if _player_instance is None:
        _player_instance = MusicPlayer()
    return _player_instance

