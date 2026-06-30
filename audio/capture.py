"""
Audio sink: plays the PCM tapped from the main VLC player and feeds the
spectrum analyzer from those very same samples.

The main Player (player/player.py) decodes the stream and, instead of letting
VLC write to the sound card, hands every decoded buffer to AudioCapture.feed().
AudioCapture queues those frames and a sounddevice output stream pulls them to
the speakers.  The FFT buffer the SpectrumAnalyzer reads is filled from the
frames at the moment they are sent to the device, so the display matches what is
actually heard -- a single decode and a single connection, with no second stream
to drift out of phase.
"""
import collections
import ctypes
import logging
import threading
import time

import numpy as np

try:
    import sounddevice as sd
except Exception as exc:  # pragma: no cover - missing PortAudio / sounddevice
    sd = None
    logging.warning(f"sounddevice unavailable, falling back to VLC output: {exc}")

FFT_SIZE = 4096
CHANNELS = 2
RATE = 44100             # forced via Player.audio_set_format; VLC resamples to it
BLOCKSIZE = 1024         # frames per output callback (~23 ms @ 44.1 kHz)
_MAX_QUEUED_CHUNKS = 48  # ceiling on buffered audio; bounds latency / drift build-up


class AudioCapture:
    """
    Persistent audio sink shared by the controller and the SpectrumAnalyzer.

    It outlives station changes: the Player is recreated on every change and
    feeds whichever AudioCapture instance it was handed.  Producer side (feed)
    runs on VLC's audio thread; consumer side (_output_cb) runs on PortAudio's
    thread; the two meet over a lock-protected chunk queue.
    """

    # Exposed so SpectrumAnalyzer can size its FFT bins to the real sample rate.
    _RATE = RATE

    def __init__(self):
        self._fft_buffer = np.zeros(FFT_SIZE, dtype=np.float32)
        self._queue = collections.deque(maxlen=_MAX_QUEUED_CHUNKS)
        self._residual = np.zeros((0, CHANNELS), dtype=np.float32)
        self._lock = threading.Lock()
        self._last_feed = 0.0
        self._stream = None

    # ------------------------------------------------------------------
    # Public API (consumed by SpectrumAnalyzer / controller / main)
    # ------------------------------------------------------------------

    @property
    def output_available(self):
        """True when we can drive the sound card ourselves (sounddevice present)."""
        return sd is not None

    @property
    def is_active(self):
        return (time.monotonic() - self._last_feed) < 0.5

    def get_samples(self):
        with self._lock:
            return self._fft_buffer.copy()

    def start(self, station: str = None):
        """Open the output stream (once) and drop stale audio on a station change."""
        self.flush()
        self._last_feed = 0.0
        self._ensure_stream()

    def flush(self):
        with self._lock:
            self._queue.clear()
            self._residual = np.zeros((0, CHANNELS), dtype=np.float32)

    def close(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    # ------------------------------------------------------------------
    # Producer side: called from the Player's VLC audio thread
    # ------------------------------------------------------------------

    def feed(self, samples, count):
        """Convert one VLC S16N stereo buffer to float32 frames and queue it."""
        try:
            n_shorts = count * CHANNELS
            addr = ctypes.cast(samples, ctypes.c_void_p).value
            raw = (ctypes.c_int16 * n_shorts).from_address(addr)
            frames = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            frames = frames.reshape(-1, CHANNELS)
            with self._lock:
                self._queue.append(frames)
            self._last_feed = time.monotonic()
        except Exception as exc:
            logging.debug(f"AudioCapture.feed: {exc}")

    # ------------------------------------------------------------------
    # Consumer side: sounddevice output callback (PortAudio thread)
    # ------------------------------------------------------------------

    def _ensure_stream(self):
        if self._stream is not None or sd is None:
            return
        try:
            self._stream = sd.OutputStream(
                samplerate=RATE, channels=CHANNELS, dtype='float32',
                blocksize=BLOCKSIZE, callback=self._output_cb,
            )
            self._stream.start()
        except Exception as exc:
            logging.warning(f"AudioCapture: could not open output stream: {exc}")
            self._stream = None

    def _output_cb(self, outdata, frames, time_info, status):
        try:
            filled = 0
            with self._lock:
                while filled < frames:
                    if len(self._residual):
                        take = min(frames - filled, len(self._residual))
                        outdata[filled:filled + take] = self._residual[:take]
                        self._residual = self._residual[take:]
                        filled += take
                    elif self._queue:
                        self._residual = self._queue.popleft()
                    else:
                        break
                if filled < frames:
                    outdata[filled:] = 0.0  # underrun -> brief silence
                # Fill the FFT buffer from exactly what is going to the device,
                # so the spectrum is aligned with what is heard.
                if filled:
                    mono = outdata[:filled].mean(axis=1)
                    n = len(mono)
                    if n >= FFT_SIZE:
                        self._fft_buffer = mono[-FFT_SIZE:].astype(np.float32)
                    else:
                        self._fft_buffer = np.roll(self._fft_buffer, -n)
                        self._fft_buffer[-n:] = mono
        except Exception as exc:
            logging.debug(f"AudioCapture._output_cb: {exc}")
            outdata.fill(0.0)
