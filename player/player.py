# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Olivier Meyer

# Standard library
import ctypes
import logging
import sys
import threading
# Third party
import vlc

# Local imports
from player.constants import STREAM_URLS_MP3, STREAM_URLS_AAC, NETWORK_CACHING_MS
from audio.capture import CHANNELS
from player_settings import PlayerSettings

settings = PlayerSettings()

# libvlc audio callback signatures (mirror the libvlc_audio_*_cb typedefs)
_PlayCb   = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_int64)
_PauseCb  = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int64)
_ResumeCb = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int64)
_FlushCb  = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int64)
_DrainCb  = ctypes.CFUNCTYPE(None, ctypes.c_void_p)


class Player:
    def __init__(self, station, sink=None):
        self._station = station
        self._sink = sink
        stream_url = STREAM_URLS_MP3[station] if settings.quality == 'midfi' else STREAM_URLS_AAC[station]

        try:
            self._instance = vlc.Instance("--quiet", "--no-video-title-show", "--intf", "dummy")
            self._player = self._instance.media_player_new()
            media = self._instance.media_new(stream_url)
            media.add_option(f":network-caching={NETWORK_CACHING_MS}")
            self._player.set_media(media)
            self._attach_sink()
        except Exception as e:
            logging.critical(f'Error initializing VLC player from {stream_url}: {e}', exc_info=True)
            sys.exit()

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, args=(self._stop_event,))
        self._thread.start()

    def _attach_sink(self):
        """
        Route decoded PCM to the shared AudioCapture instead of the sound card,
        so a single decode feeds both the speakers and the spectrum. If no usable
        sink is available (sounddevice missing), leave VLC to play normally; the
        spectrum simply stays idle.
        """
        if self._sink is None or not self._sink.output_available:
            return

        def play_cb(opaque, samples, count, pts):
            self._sink.feed(samples, count)

        # Keep ctypes callbacks referenced so the GC won't free them mid-stream.
        self._play_cb = _PlayCb(play_cb)
        self._noop_cbs = [
            _PauseCb(lambda *_: None), _ResumeCb(lambda *_: None),
            _FlushCb(lambda *_: None), _DrainCb(lambda *_: None),
        ]
        self._player.audio_set_callbacks(
            self._play_cb,
            self._noop_cbs[0], self._noop_cbs[1],
            self._noop_cbs[2], self._noop_cbs[3],
            None,
        )
        # Force decode to S16N stereo at the sink's actual rate; VLC resamples.
        self._player.audio_set_format("S16N", int(self._sink.samplerate), CHANNELS)

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
        # When pausing, drop buffered audio so the mute is immediate instead of
        # playing out the queue tail.
        if self._sink is not None and not self._player.is_playing():
            self._sink.flush()
