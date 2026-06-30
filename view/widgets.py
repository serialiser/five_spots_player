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
    FFT_SIZE = 4096     # 4096 @ 44.1 kHz -> ~10.8 Hz/bin (was 2048 -> 21.5 Hz),
                        # so the low bands resolve real detail instead of clones
    F_MIN   = 40.0      # FIP is broadcast; near-nothing lives below 40 Hz, and
                        # starting lower only starves the bottom bands of bins
    F_MAX   = 16_000.0

    # --- bar geometry ---
    BAR_W    = 9    # bar width, px
    BAR_GAP  = 2    # horizontal gap between bars, px
    SEG_H    = 4    # LED segment height, px
    SEG_GAP  = 2    # vertical gap between segments, px
    SLOT_H   = 80   # available vertical space, px

    # --- animation (60 fps) ---
    FALL_PX      = 9     # bar descent, px/frame (higher = snappier, tracks rhythm)
    PEAK_HOLD_F  = 12    # frames the peak marker hangs before it drops (0.25 s)
    PEAK_GRAVITY = 0.18  # peak fall acceleration, px/frame²: the marker starts slow
                         # then speeds up as it drops, like a falling object (Winamp)
    PEAK_FALL_PX = 2     # linear peak descent, px/frame — used only to clear the
                         # display when the audio is inactive (paused / switching)

    # --- level mapping (perceptual dB) ---
    # Band energy is summed (see _band_levels), mapped to dB, then tilted to lift
    # the highs that music's ~1/f roll-off leaves low. The display is a dB *window*
    # below an auto-gain ceiling. Tuned here for musical *fidelity*: a slow ceiling
    # and a wide window so loud and quiet passages actually look different, rather
    # than every passage being normalised up to a constantly-full display.
    TILT_DB_OCT   = 1.5     # high-freq lift per octave above F_REF
    F_REF         = 1000.0  # pivot frequency: tilt leaves this band unchanged
    DISPLAY_RANGE_DB = 42.0  # dB window shown below the ceiling -- wide, so musical
                             # dynamics are visible (smaller = more contrast/emptier)
    HEADROOM_DB   = 4.0     # space kept above the loudest band so the top isn't
                            # pinned permanently (only transients reach it)
    CEIL_MIN_DB   = -58.0   # lowest the ceiling may fall, so near-silence reads as
                            # quiet instead of being amplified into a full display
    CEIL_DECAY_DB = 0.02    # auto-gain ceiling fall rate (≈1.2 dB/s @ 60 fps): slow,
                            # so a loud peak isn't immediately followed by a pumped-up
                            # quiet passage -- the forte/piano contrast survives
    GAMMA         = 1.2     # ~linear dB for a truer mapping (>1 pushes mids down)
    DB_SMOOTH     = 0.6     # temporal EMA on band dB (1.0 = off): tames single-frame
                            # FFT noise without visibly slowing the response
    BAR_SMOOTH    = 0.15    # light neighbour blending (0 = off): a touch of spatial
                            # cohesion without smearing real spectral detail

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
        self._peak_vel   = np.zeros(self.N_BARS, dtype=np.float64)  # gravity fall speed
        self._db_ema     = np.full(self.N_BARS, -120.0, dtype=np.float64)

        # Hann window for FFT
        self._hann = np.hanning(self.FFT_SIZE)

        # Auto-gain ceiling (in dB); starts at its minimum
        self._agc_ceil = self.CEIL_MIN_DB

        # Log-spaced frequency edges → FFT-bin index ranges
        sample_rate = getattr(capture, '_RATE', 44100)
        edges = np.logspace(np.log10(self.F_MIN), np.log10(self.F_MAX), self.N_BARS + 1)
        fft_freqs = np.fft.rfftfreq(self.FFT_SIZE, 1.0 / sample_rate)
        self._band_bins: list[np.ndarray] = []
        anchored: list[bool] = []
        for i in range(self.N_BARS):
            mask = (fft_freqs >= edges[i]) & (fft_freqs < edges[i + 1])
            idxs = np.where(mask)[0]
            if len(idxs) == 0:
                # Band narrower than one FFT bin: borrow the nearest bin, but flag
                # it so _band_levels interpolates rather than showing a duplicate.
                idxs = np.array([np.argmin(np.abs(fft_freqs - (edges[i] + edges[i + 1]) / 2))])
                anchored.append(False)
            else:
                anchored.append(True)
            self._band_bins.append(idxs)
        # True where the band holds at least one real FFT bin (an interpolation
        # anchor); starved bands between anchors are filled in _band_levels.
        self._anchored = np.array(anchored, dtype=bool)

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
        # Sum (not mean) the bins in each band: mean divides the wide treble bands
        # by their bin count and crushes the highs; the sum is the band's energy.
        band_power = np.array([power[b].sum() for b in self._band_bins])
        db = 10.0 * np.log10(band_power + 1e-12)
        # Fill bands too narrow to own a bin by interpolating between the anchored
        # bands, so the bass is a smooth curve instead of lock-step duplicates.
        if self._anchored.any() and not self._anchored.all():
            idx = np.arange(self.N_BARS)
            db = np.interp(idx, idx[self._anchored], db[self._anchored])
        return db + self._tilt_db

    def update(self):
        """Advance physics (FFT, auto-gain, smoothing, peaks). Call once per frame."""
        if not self._capture.is_active:
            self._heights = np.maximum(self._heights - self.FALL_PX, 0)
            self._peak_h  = np.maximum(self._peak_h  - self.PEAK_FALL_PX, 0)
            return

        # Temporal smoothing: an exponential moving average on the band dB removes
        # single-frame FFT jitter before the attack/decay below, so bars track the
        # music instead of flickering on spectral noise.
        db = self._band_levels()
        self._db_ema = self.DB_SMOOTH * db + (1.0 - self.DB_SMOOTH) * self._db_ema
        db = self._db_ema

        # Auto-gain: ceiling jumps up to the loudest band (plus headroom so the
        # top stays free for transients), then slips back down slowly. The shown
        # window is a fixed dB span below it, so a band well under the peak drops
        # off quickly -> contrast stays constant whatever the volume.
        self._agc_ceil = max(self._agc_ceil - self.CEIL_DECAY_DB,
                             db.max() + self.HEADROOM_DB,
                             self.CEIL_MIN_DB)
        floor = self._agc_ceil - self.DISPLAY_RANGE_DB
        normalised = (db - floor) / self.DISPLAY_RANGE_DB
        # Gamma maps the dB window to bar height (≈linear here for a truer display).
        normalised = np.clip(normalised, 0.0, 1.0) ** self.GAMMA
        # Light neighbour blending for spatial cohesion without smearing detail.
        if self.BAR_SMOOTH > 0.0:
            blended = normalised.copy()
            blended[1:-1] = ((1.0 - self.BAR_SMOOTH) * normalised[1:-1]
                             + 0.5 * self.BAR_SMOOTH * (normalised[:-2] + normalised[2:]))
            normalised = blended
        target = normalised * self._max_h

        for i in range(self.N_BARS):
            t = target[i]
            h = self._heights[i]

            # Fast rise, slow fall
            self._heights[i] = t if t >= h else max(h - self.FALL_PX, t)

            # Peak: hang for PEAK_HOLD_F frames, then fall under gravity. Each frame
            # of the fall adds to the velocity, so the marker accelerates downward;
            # a new high re-arms the marker and resets the fall to rest.
            if self._heights[i] >= self._peak_h[i]:
                self._peak_h[i]    = self._heights[i]
                self._peak_hold[i] = self.PEAK_HOLD_F
                self._peak_vel[i]  = 0.0
            elif self._peak_hold[i] > 0:
                self._peak_hold[i] -= 1
            else:
                self._peak_vel[i] += self.PEAK_GRAVITY
                self._peak_h[i] = max(self._peak_h[i] - self._peak_vel[i], 0)

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
