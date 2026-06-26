# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Olivier Meyer

# Standard library
import time

# Third party
import numpy as np
import pygame

# Local imports
from view.constants import COLORS


class TrackTimer:
    def __init__(self, nb_seconds):
        self.nb_seconds = nb_seconds
        self.running = False
        self.seconds_remaining = 0
        self.reached_zero = False
        self.seconds_at_end = None

    def start(self, new_starting_seconds=None):
        seconds_now = time.time()
        if new_starting_seconds is not None:
            self.nb_seconds = new_starting_seconds
        self.seconds_at_end = seconds_now + self.nb_seconds
        self.reached_zero = False
        self.running = True
        
    def stop(self):
        self.get_remaining_seconds()
        self.running = False

    def get_remaining_seconds(self):
        if not self.running:
            return self.seconds_remaining

        self.seconds_remaining = int(self.seconds_at_end - time.time())

        if self.seconds_remaining <= 0:
            self.seconds_remaining = 0.0
            self.running = False
            self.reached_zero = True

        return self.seconds_remaining

    def get_remaining_time(self):
        nb_seconds = self.get_remaining_seconds()
        mins, secs = divmod(nb_seconds, 60)
        hours, mins = divmod(int(mins), 60)

        if hours > 0:
            time_in_hhmmss = f'{hours:d}:{mins:02d}:{secs:02.0f}'
        else:
            time_in_hhmmss = f'{mins:02d}:{secs:02.0f}'

        return time_in_hhmmss


class TimeBar:
    def __init__(self, surf, pos, size, bgcolor, bar_color):
        self.surf = surf
        self.pos = pos
        self.size = size
        self.bgcolor = bgcolor
        self.bar_color = bar_color
        self.progress = 0
        self.bar_size = 0

    def draw(self, progress):
        self.progress = progress
        self.bar_size = ((self.size[0]) * self.progress, self.size[1])
        pygame.draw.rect(self.surf, self.bgcolor, (*self.pos, *self.size), 0)
        pygame.draw.rect(self.surf, self.bar_color, (*self.pos, *self.bar_size))


class TextWidget:

    def __init__(self, window, loc, value, text_color, font, size):
        pygame.font.init()
        self.window = window
        self.loc = loc
        self.font = pygame.font.Font(font, size)
        self.text_color = text_color
        self.text = ""
        self.text_surface = self.font.render(self.text, True, self.text_color)
        self.set_value(value)

    def set_value(self, new_text):
        if new_text is None:
            new_text = ''
        if self.text == new_text:
            return
        self.text = new_text
        self.text_surface = self.font.render(self.text, True, self.text_color)

    def draw(self):
        self.window.blit(self.text_surface, self.loc)


class LinkWidget:
    """Clickable text that behaves like a hyperlink (hand cursor + underline on hover)."""

    def __init__(self, window, loc, value, text_color, font, size, url='#'):
        pygame.font.init()
        self.window = window
        self.loc = loc
        self.url = url
        self.font = pygame.font.Font(font, size)
        self.text_color = text_color
        self.text = value
        self.text_surface = self.font.render(self.text, True, self.text_color)
        self.rect = self.text_surface.get_rect(topleft=loc)
        self.hover = False

    def handle_event(self, event_obj):
        if event_obj.type == pygame.MOUSEBUTTONUP and self.rect.collidepoint(event_obj.pos):
            return True
        return False

    def update_hover(self):
        self.hover = self.rect.collidepoint(pygame.mouse.get_pos())
        if self.hover:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)

    def draw(self):
        self.window.blit(self.text_surface, self.loc)
        if self.hover:
            y = self.loc[1] + self.text_surface.get_height() - 1
            pygame.draw.line(self.window, self.text_color, (self.loc[0], y),
                             (self.loc[0] + self.text_surface.get_width(), y), 1)


class ButtonWidget:

    def __init__(self, window, loc, up, down):
        self.window = window
        self.loc = loc
        self.surface_up = pygame.image.load(up)
        self.surface_down = pygame.image.load(down)

        self.hover = False
        self.clicked = False
        self.active = False

        self.rect = self.surface_up.get_rect()
        self.rect[0] = loc[0]
        self.rect[1] = loc[1]

    def handle_event(self, event_obj):

        if event_obj.type not in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP, pygame.MOUSEBUTTONDOWN):
            return False

        if (event_obj.type == pygame.MOUSEBUTTONUP) and self.rect.collidepoint(event_obj.pos):
            self.clicked = True
            self.active = not self.active
            return True

        return False

    def update_hover(self):
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        if hover:
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)

    def draw(self):
        if self.active:
            self.window.blit(self.surface_down, self.loc)
        else:
            self.window.blit(self.surface_up, self.loc)


class SpectrumAnalyzer:
    """
    Winamp-style LED-segment spectrum analyzer for pygame.

    Geometry (fits a 530 x 80 px slot starting at pos):
      48 bars x (9 px wide + 2 px gap) = 526 px total width
      13 LED segments x (4 px high + 2 px gap) = 78 px total height

    Colour gradient per bar:  dark-blue (bottom) → cyan → white (top).
    Each bar has a peak marker: hold PEAK_HOLD_F frames, then fall.

    Levels are mapped perceptually (dB) with a high-frequency tilt so the
    display stays balanced across the spectrum instead of clustering in the
    bass, and an auto-gain ceiling keeps it well-filled at any volume.

    Call update() then draw() once per frame.
    """

    # --- frequency range ---
    N_BARS  = 48
    FFT_SIZE = 2048
    F_MIN   = 20.0
    F_MAX   = 16_000.0

    # --- bar geometry ---
    BAR_W    = 9    # bar width, px
    BAR_GAP  = 2    # horizontal gap between bars, px
    SEG_H    = 4    # LED segment height, px
    SEG_GAP  = 2    # vertical gap between segments, px
    SLOT_H   = 80   # available vertical space, px

    # --- animation (60 fps) ---
    FALL_PX      = 9    # bar descent, px/frame (higher = snappier, tracks rhythm)
    PEAK_HOLD_F  = 15   # frames before peak falls  (0.25 s @ 60 fps)
    PEAK_FALL_PX = 2    # peak descent, px/frame

    # --- level mapping (perceptual dB) ---
    # Music rolls off ~1/f, so a linear magnitude display clusters in the bass.
    # We map band power to dB and add a per-octave tilt that lifts the highs.
    # The display shows a fixed dB *window* below an auto-gain ceiling that
    # tracks the loudest band, so contrast stays the same at any volume.
    TILT_DB_OCT   = 2.2     # high-freq lift per octave above F_REF (0 = flat)
    F_REF         = 1000.0  # pivot frequency: tilt leaves this band unchanged
    DISPLAY_RANGE_DB = 32.0  # dB window shown below the ceiling (smaller = more
                             # contrast, emptier; larger = fuller)
    HEADROOM_DB   = 6.0     # space kept above the loudest band so the top isn't
                            # pinned permanently (only transients reach it)
    CEIL_MIN_DB   = -52.0   # lowest the ceiling may fall, so near-silence isn't
                            # amplified into a full display
    CEIL_DECAY_DB = 0.06    # auto-gain ceiling fall rate (≈3.6 dB/s @ 60 fps)
    GAMMA         = 1.7     # >1 pushes mid/low levels down: more dynamic, less
                            # constantly-filled (1.0 = linear dB, fuller look)

    def __init__(self, window, pos, capture):
        """
        window  : pygame surface (the main window)
        pos     : (x, y) top-left corner of the spectrum slot
        capture : AudioCapture instance
        """
        self._window  = window
        self._x, self._y = pos
        self._capture = capture

        # Effective max height snapped to the segment grid
        self._seg_px  = self.SEG_H + self.SEG_GAP          # 6 px/segment
        self._n_segs  = self.SLOT_H // self._seg_px         # 13 segments
        self._max_h   = self._n_segs * self._seg_px          # 78 px

        # Per-bar state
        self._heights    = np.zeros(self.N_BARS, dtype=np.float64)
        self._peak_h     = np.zeros(self.N_BARS, dtype=np.float64)
        self._peak_hold  = np.zeros(self.N_BARS, dtype=np.int32)

        # Hann window for FFT
        self._hann = np.hanning(self.FFT_SIZE)

        # Auto-gain ceiling (in dB); starts at its minimum
        self._agc_ceil = self.CEIL_MIN_DB

        # Log-spaced frequency edges → FFT-bin index ranges
        sample_rate = getattr(capture, '_RATE', 44100)
        edges = np.logspace(np.log10(self.F_MIN), np.log10(self.F_MAX), self.N_BARS + 1)
        fft_freqs = np.fft.rfftfreq(self.FFT_SIZE, 1.0 / sample_rate)
        self._band_bins: list[np.ndarray] = []
        for i in range(self.N_BARS):
            mask = (fft_freqs >= edges[i]) & (fft_freqs < edges[i + 1])
            idxs = np.where(mask)[0]
            if len(idxs) == 0:
                idxs = np.array([np.argmin(np.abs(fft_freqs - (edges[i] + edges[i + 1]) / 2))])
            self._band_bins.append(idxs)

        # Per-band high-frequency tilt (dB): +TILT_DB_OCT per octave above F_REF,
        # negative below, so the bass no longer dominates the display.
        centers = np.sqrt(edges[:-1] * edges[1:])
        self._tilt_db = self.TILT_DB_OCT * np.log2(centers / self.F_REF)

        # Precompute gradient: index 0 = bottom (midblue), last = top (white)
        mb = COLORS['midblue']  # (52, 152, 219)
        self._gradient: list[tuple[int, int, int]] = []
        for i in range(self._n_segs):
            t = i / max(self._n_segs - 1, 1)
            if t < 0.5:
                t2 = t * 2
                r = int(mb[0] * (1 - t2))
                g = int(mb[1] + (255 - mb[1]) * t2)
                b = int(mb[2] + (255 - mb[2]) * t2)
                self._gradient.append((r, g, b))           # midblue → cyan
            else:
                t2 = (t - 0.5) * 2
                self._gradient.append((int(t2 * 255), 255, 255))  # cyan → white

    # ------------------------------------------------------------------
    def _band_levels(self) -> np.ndarray:
        """Per-band level in dB, with the high-frequency tilt applied."""
        samples = self._capture.get_samples()
        power = np.abs(np.fft.rfft(samples * self._hann)) ** 2
        band_power = np.array([power[b].mean() for b in self._band_bins])
        db = 10.0 * np.log10(band_power + 1e-12)
        return db + self._tilt_db

    def update(self):
        """Advance physics (FFT, auto-gain, smoothing, peaks). Call once per frame."""
        if not self._capture.is_active:
            self._heights = np.maximum(self._heights - self.FALL_PX, 0)
            self._peak_h  = np.maximum(self._peak_h  - self.PEAK_FALL_PX, 0)
            return

        db = self._band_levels()

        # Auto-gain: ceiling jumps up to the loudest band (plus headroom so the
        # top stays free for transients), then slips back down slowly. The shown
        # window is a fixed dB span below it, so a band well under the peak drops
        # off quickly -> contrast stays constant whatever the volume.
        self._agc_ceil = max(self._agc_ceil - self.CEIL_DECAY_DB,
                             db.max() + self.HEADROOM_DB,
                             self.CEIL_MIN_DB)
        floor = self._agc_ceil - self.DISPLAY_RANGE_DB
        normalised = (db - floor) / self.DISPLAY_RANGE_DB
        # Gamma expansion pushes everything but the peaks down for a livelier,
        # less saturated display while keeping the spectral balance intact.
        normalised = np.clip(normalised, 0.0, 1.0) ** self.GAMMA
        target = normalised * self._max_h

        for i in range(self.N_BARS):
            t = target[i]
            h = self._heights[i]

            # Fast rise, slow fall
            self._heights[i] = t if t >= h else max(h - self.FALL_PX, t)

            # Peak: hold then fall
            if self._heights[i] >= self._peak_h[i]:
                self._peak_h[i]    = self._heights[i]
                self._peak_hold[i] = self.PEAK_HOLD_F
            elif self._peak_hold[i] > 0:
                self._peak_hold[i] -= 1
            else:
                self._peak_h[i] = max(self._peak_h[i] - self.PEAK_FALL_PX, 0)

    def draw(self):
        """Render bars + peak markers directly onto the window surface."""
        bottom = self._y + self._max_h

        for i in range(self.N_BARS):
            bx    = self._x + i * (self.BAR_W + self.BAR_GAP)
            n_lit = int(self._heights[i] / self._seg_px)

            # LED segments (bottom to top)
            for s in range(n_lit):
                sy    = bottom - (s + 1) * self._seg_px
                color = self._gradient[min(s, self._n_segs - 1)]
                pygame.draw.rect(self._window, color, (bx, sy, self.BAR_W, self.SEG_H))

            # Peak marker (drawn one segment above the bar top)
            ps = int(self._peak_h[i] / self._seg_px)
            if 0 < ps <= self._n_segs and ps > n_lit:
                py       = bottom - ps * self._seg_px
                pk_color = self._gradient[min(ps - 1, self._n_segs - 1)]
                pygame.draw.rect(self._window, pk_color, (bx, py, self.BAR_W, self.SEG_H))
