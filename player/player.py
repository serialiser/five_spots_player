# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Olivier Meyer

# Standard library
import logging
import sys
import threading
# Third party
import vlc

# Local imports
from player.constants import STREAM_URLS_MP3, STREAM_URLS_AAC, NETWORK_CACHING_MS
from player_settings import PlayerSettings

settings = PlayerSettings()


class Player:
    def __init__(self, station):
        self._station = station
        stream_url = STREAM_URLS_MP3[station] if settings.quality == 'midfi' else STREAM_URLS_AAC[station]

        try:
            self._instance = vlc.Instance("--quiet", "--no-video-title-show", "--intf", "dummy")
            self._player = self._instance.media_player_new()
            media = self._instance.media_new(stream_url)
            # Match the capture player's buffering so the spectrum stays in sync.
            media.add_option(f":network-caching={NETWORK_CACHING_MS}")
            self._player.set_media(media)
        except Exception as e:
            logging.critical(f'Error initializing VLC player from {stream_url}: {e}', exc_info=True)
            sys.exit()

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, args=(self._stop_event,))
        self._thread.start()

    def _run(self, stop_event):
        try:
            self._player.play()
            while not stop_event.is_set():
                stop_event.wait(timeout=1)
            self._player.stop()
        except Exception as e:
            logging.critical(f'Error in VLC player thread: {e}', exc_info=True)

    def close(self):
        self._stop_event.set()
        self._thread.join()

    def play_or_pause(self):
        self._player.pause()
