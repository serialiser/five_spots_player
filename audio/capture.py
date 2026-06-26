"""
PCM capture via VLC audio callbacks (audio_set_callbacks / audio_set_format).

A silent secondary VLC player decodes the same stream as the main player and
routes its output to a Python callback instead of the hardware.  The callback
fills a rolling float32 buffer that the SpectrumAnalyzer reads for FFT.
"""
import ctypes
import logging
import threading

import numpy as np
import vlc

from player.constants import STREAM_URLS_MP3, STREAM_URLS_AAC, NETWORK_CACHING_MS
from player_settings import PlayerSettings

FFT_SIZE = 2048
_CHANNELS = 2
_RATE = 44100   # forced via audio_set_format; VLC will resample if needed

# --------------------------------------------------------------------------
# ctypes callback signatures (mirror libvlc_audio_*_cb typedefs)
# --------------------------------------------------------------------------
_PlayCb   = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_int64)
_PauseCb  = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int64)
_ResumeCb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int64)
_FlushCb  = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int64)
_DrainCb  = ctypes.CFUNCTYPE(None, ctypes.c_void_p)


class AudioCapture:
    """
    Feeds a rolling PCM buffer from a silent VLC player using audio callbacks.
    Call start(station) each time the station changes.
    """

    def __init__(self):
        self._buffer = np.zeros(FFT_SIZE, dtype=np.float32)
        self._lock = threading.Lock()
        self._active = False

        # VLC objects, kept alive to prevent GC
        self._instance = None
        self._player = None
        self._play_cb = None      # ctypes keeps them alive via attribute refs
        self._noop_cbs = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_active(self):
        return self._active

    def get_samples(self):
        with self._lock:
            return self._buffer.copy()

    def start(self, station: str):
        """Start (or restart) PCM capture for the given station key."""
        self._stop_player()

        settings = PlayerSettings()
        urls = STREAM_URLS_MP3 if settings.quality == 'midfi' else STREAM_URLS_AAC
        url = urls.get(station)
        if not url:
            return

        try:
            self._launch(url)
        except Exception as exc:
            logging.warning(f"AudioCapture.start failed: {exc}")

    def close(self):
        self._stop_player()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _stop_player(self):
        if self._player:
            try:
                self._player.stop()
            except Exception:
                pass
            self._player = None
        self._active = False

    def _launch(self, url: str):
        instance = vlc.Instance("--quiet", "--no-video")
        player = instance.media_player_new()
        media = instance.media_new(url)
        # Match the main player's buffering so the spectrum stays in sync.
        media.add_option(f":network-caching={NETWORK_CACHING_MS}")
        player.set_media(media)

        # Build ctypes callbacks — must stay referenced so GC won't free them
        def play_cb(*args):
            # args: (opaque, samples, count, pts) — only samples and count used
            samples, count = args[1], args[2]
            n_shorts = count * _CHANNELS
            try:
                addr = ctypes.cast(samples, ctypes.c_void_p).value
                raw = (ctypes.c_int16 * n_shorts).from_address(addr)
                arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                mono = arr.reshape(-1, _CHANNELS).mean(axis=1)
                n = len(mono)
                with self._lock:
                    self._buffer = np.roll(self._buffer, -n)
                    self._buffer[-n:] = mono[:FFT_SIZE]
            except Exception as exc:
                logging.debug(f"AudioCapture play_cb: {exc}")

        self._play_cb  = _PlayCb(play_cb)
        self._noop_cbs = [
            _PauseCb(lambda *_: None), _ResumeCb(lambda *_: None),
            _FlushCb(lambda *_: None), _DrainCb(lambda *_: None),
        ]

        player.audio_set_callbacks(
            self._play_cb,
            self._noop_cbs[0], self._noop_cbs[1],
            self._noop_cbs[2], self._noop_cbs[3],
            None,
        )
        # Force decode to S16N stereo at _RATE — VLC resamples automatically
        player.audio_set_format("S16N", _RATE, _CHANNELS)

        player.play()

        self._instance = instance
        self._player = player
        self._active = True
