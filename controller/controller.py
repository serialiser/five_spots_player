# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Olivier Meyer

# Standard library
import asyncio

# Third party
import pygame

# Local imports
from player.player import Player
from model.tracks import Tracks
from view.view import View
from view.constants import FONTS, COLORS


class Controller:
    """
    Controls the display (view), the radio stream (via player) and the track data (model).
    """
    def __init__(self, window, audio_capture=None):
        self._window = window
        self._view = View(self._window)
        self._tracks = Tracks()
        self._stream = None
        self._current_station = None
        self._state = 'play'
        self._audio_capture = audio_capture

    @property
    def view(self):
        return self._view

    @property
    def tracks(self):
        return self._tracks

    @property
    def current_station(self):
        return self._current_station

    @property
    def state(self):
        return self._state

    @property
    def stream(self):
        return self._stream

    def create_stream(self, station):
        self._stream = Player(station, sink=self._audio_capture)
        self._current_station = station
        self._state = 'play'
        if self._audio_capture is not None:
            self._audio_capture.start(station)
        return self._stream

    def set_state(self, state):
        self._state = state

    def play_or_pause(self):
        self._stream.play_or_pause()

    def close_stream(self):
        self._stream.close()

    def update_streams(self, station):
        if self._stream is not None:
            self._stream.close()
        self.create_stream(station)

    async def update_track(self, track):
        query_data = asyncio.create_task(track.query_data())
        await query_data
        self._view.update_track(track.title, track.artists, track.album, track.year, track.label, track.end)
        query_cover = asyncio.create_task(track.query_cover())
        await query_cover
        update_cover = asyncio.create_task(self._view.update_cover(track.cover_url))
        await update_cover
        self._view.update_sync("")


class DropdownMenu:
    """
    Dropdown station selector in the top right corner.
    """
    STATIONS = [
        ('FIP', 'fip'),
        ('JAZZ', 'jazz'),
        ('ROCK', 'rock'),
        ('GROOVE', 'groove'),
        ('WORLD', 'world'),
        ('NEW REL.', 'new'),
        ('REGGAE', 'reggae'),
        ('ELECTRO', 'electro'),
        ('METAL', 'metal'),
        ('POP', 'pop'),
        ('HIP-HOP', 'hiphop'),
        ('SACRE FR.', 'sacrefrancais'),
        ('CULTES', 'cultes'),
    ]
    BTN_W = 130
    BTN_H = 27
    ITEM_H = 22

    def __init__(self, controller):
        self.controller = controller
        self._open = False
        self._selected_value = None
        self._font = pygame.font.Font(FONTS['main'], 10)
        # Align top with the cover (y=30) and right edge with the end of the timebar (x=881)
        top = 30
        right = 881
        x = right - self.BTN_W
        self._btn_rect = pygame.Rect(x, top, self.BTN_W, self.BTN_H)
        self._item_rects = [
            pygame.Rect(x, top + self.BTN_H + i * self.ITEM_H, self.BTN_W, self.ITEM_H)
            for i in range(len(self.STATIONS))
        ]

    PAD_X = 10

    def _btn_label(self):
        if self._selected_value:
            return next(lbl for lbl, val in self.STATIONS if val == self._selected_value)
        return 'Station'

    def close(self):
        self._open = False

    def update(self, event_list):
        mouse_pos = pygame.mouse.get_pos()

        if self._btn_rect.collidepoint(mouse_pos):
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
        elif self._open:
            for rect in self._item_rects:
                if rect.collidepoint(mouse_pos):
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                    break

        for event in event_list:
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self._btn_rect.collidepoint(mouse_pos):
                    self._open = not self._open
                elif self._open:
                    for i, rect in enumerate(self._item_rects):
                        if rect.collidepoint(mouse_pos):
                            _, value = self.STATIONS[i]
                            self._open = False
                            self.activate_station(value)
                            break
                    else:
                        self._open = False

    def activate_station(self, value):
        self._selected_value = value
        self.controller.view.timer.stop()
        self.controller.update_streams(value)
        track = self.controller.tracks.get_or_create_track(value)
        asyncio.run(self.controller.update_track(track))
        self.controller.view.update_sync(track.sync_msg)
        self.controller.view.button_mute.active = False
        self.controller.view.button_like.active = bool(track.bookmarked)

    def _draw_arrow(self, surface, rect, color):
        """Draws a downward (or upward when open) triangle on the right side of rect."""
        cx = rect.right - 14
        cy = rect.centery
        half_w = 5
        half_h = 3
        if self._open:
            points = [(cx - half_w, cy + half_h), (cx + half_w, cy + half_h), (cx, cy - half_h)]
        else:
            points = [(cx - half_w, cy - half_h), (cx + half_w, cy - half_h), (cx, cy + half_h)]
        pygame.draw.polygon(surface, color, points)

    def draw(self, surface):
        mouse_pos = pygame.mouse.get_pos()
        hover_btn = self._btn_rect.collidepoint(mouse_pos)
        active = hover_btn or self._open

        # Field: light background with a border, like a real select control
        pygame.draw.rect(surface, COLORS['bgcolor'], self._btn_rect, border_radius=4)
        border_color = COLORS['heavyblue'] if active else COLORS['lightgrey']
        pygame.draw.rect(surface, border_color, self._btn_rect, width=1, border_radius=4)

        text_color = COLORS['text'] if self._selected_value else COLORS['midgrey']
        label_surf = self._font.render(self._btn_label(), True, text_color)
        surface.blit(label_surf, label_surf.get_rect(
            midleft=(self._btn_rect.left + self.PAD_X, self._btn_rect.centery)))
        self._draw_arrow(surface, self._btn_rect, COLORS['othergrey'])

        if not self._open:
            return

        # Open list: single panel with border, left-aligned items
        list_rect = pygame.Rect(self._item_rects[0].left, self._item_rects[0].top,
                                self.BTN_W, self.ITEM_H * len(self.STATIONS))
        pygame.draw.rect(surface, COLORS['bgcolor'], list_rect)

        for i, (label, value) in enumerate(self.STATIONS):
            rect = self._item_rects[i]
            hover = rect.collidepoint(mouse_pos)
            is_selected = value == self._selected_value
            if hover:
                pygame.draw.rect(surface, COLORS['heavyblue'], rect)
                item_color = COLORS['textbutton']
            elif is_selected:
                pygame.draw.rect(surface, COLORS['verylightgrey'], rect)
                item_color = COLORS['heavyblue']
            else:
                item_color = COLORS['text']
            item_surf = self._font.render(label, True, item_color)
            surface.blit(item_surf, item_surf.get_rect(
                midleft=(rect.left + self.PAD_X, rect.centery)))

        pygame.draw.rect(surface, COLORS['lightgrey'], list_rect, width=1)
