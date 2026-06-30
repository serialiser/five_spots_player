# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Olivier Meyer

# Standard library
import json
import logging
from pathlib import Path

# Third party
import spotipy
from spotipy.oauth2 import SpotifyPKCE
from decouple import config

SPOTIPY_CLIENT_ID = config('SPOTIPY_CLIENT_ID', default=None)
SPOTIPY_REDIRECT_URI = 'http://127.0.0.1:8080'
USER_PLAYLIST_DEFAULT_NAME = "Five spots player"
USER_PLAYLIST_PREFIX = "Five spots player"

SETTINGS_FILE = Path('settings.json')
CACHE_SPOT_AUTH = Path('.cache')


class PlayerSettings:
    """
    Settings are defined by user via main.py
    """
    _instance = None

    default_settings = {
        "quality": "hifi",  # midfi or hifi
        "spotify_sync": False,
        "unique_playlist": False,
        "dark_mode": True
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._settings = self.load_settings()
        self._quality = self._settings.get('quality', self.default_settings['quality'])
        self._spotify_sync = self._settings.get('spotify_sync', self.default_settings['spotify_sync'])
        self._unique_playlist = self._settings.get('unique_playlist', self.default_settings['unique_playlist'])
        self._dark_mode = self._settings.get('dark_mode', self.default_settings['dark_mode'])
        self._initialized = True

    @property
    def quality(self):
        return self._quality

    @property
    def spotify_sync(self):
        return self._spotify_sync

    @property
    def unique_playlist(self):
        return self._unique_playlist

    @property
    def dark_mode(self):
        return self._dark_mode

    def set_quality(self, quality):
        self._quality = quality
        self.write_settings()

    def set_spotify_sync(self, spotify_sync):
        self._spotify_sync = spotify_sync
        self.write_settings()

    def set_unique_playlist(self, unique_playlist):
        self._unique_playlist = unique_playlist
        self.write_settings()

    def set_dark_mode(self, dark_mode):
        self._dark_mode = dark_mode
        self.write_settings()

    def load_settings(self):
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r", encoding='utf-8') as f:
                try:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        # Merge over defaults so a missing/extra key never crashes the app.
                        return {**self.default_settings, **loaded}
                    logging.error("settings.json is not a JSON object, resetting to defaults")
                except json.decoder.JSONDecodeError as e:
                    logging.error(f"settings.json malformed, resetting to defaults: {e}", exc_info=True)
            return dict(self.default_settings)
        else:
            self.write_settings(default_settings=True)
            return dict(self.default_settings)

    def write_settings(self, default_settings=False):
        if default_settings is True:
            data = self.default_settings
        else:
            data = {"quality": self._quality, "spotify_sync": self._spotify_sync,
                    "unique_playlist": self._unique_playlist, "dark_mode": self._dark_mode}
        with open(SETTINGS_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)


def del_cache():
    if CACHE_SPOT_AUTH.exists():
        CACHE_SPOT_AUTH.unlink()


def spotify_connect():
    if not SPOTIPY_CLIENT_ID:
        logging.warning("Spotify not configured: SPOTIPY_CLIENT_ID missing from .env")
        return None, None
    # todo put in a thread
    try:
        spot = spotipy.Spotify(
            auth_manager=SpotifyPKCE(
                client_id=SPOTIPY_CLIENT_ID,
                redirect_uri=SPOTIPY_REDIRECT_URI,
                scope="playlist-read-private playlist-modify-private"))
        me = spot.me()
        if not me or 'id' not in me:
            logging.error("Spotify: unexpected /me response")
            return None, None
        return spot, me['id']
    except spotipy.SpotifyOauthError as e:
        logging.error(f"Spotify auth error: {e}")
        return None, None
    except Exception as e:
        logging.error(f"Spotify connect error: {e}", exc_info=True)
        return None, None
