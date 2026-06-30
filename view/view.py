# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Olivier Meyer
# Standard library
import io
import ssl
import logging

# Third party
import pygame
import aiohttp
import certifi

# Local imports
import view.widgets as widgets
from utils import resource_path
from view.constants import COLORS, FONTS, WINDOW_WIDTH, COVER_FRAME
from view.helpers import get_remaining_seconds, shorten_str
from player_settings import PlayerSettings

settings = PlayerSettings()

# Some image CDNs (e.g. Deezer) require the certifi CA bundle; the system store
# isn't always reachable for aiohttp on Windows.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class View:
    text_quality = 'MP3 128 kbps' if settings.quality == 'midfi' else 'AAC 192 kbps'

    def __init__(self, window):
        self._window = window
        self._labels = [
            widgets.TextWidget(window, (350, 91), 'Title: ', COLORS['text'], FONTS['main_bold'], 14),
            widgets.TextWidget(window, (350, 118), 'Album: ', COLORS['text'], FONTS['main_bold'], 14),
            widgets.TextWidget(window, (350, 145), 'Label: ', COLORS['text'], FONTS['main_bold'], 14)
        ]
        self._track_artist = widgets.TextWidget(window, (350, 53), '', COLORS['text'], FONTS['title'], 20)
        self._track_title = widgets.TextWidget(window, (410, 91), '', COLORS['text'], FONTS['main'], 14)
        self._track_album = widgets.TextWidget(window, (410, 118), '', COLORS['text'], FONTS['main'], 14)
        self._track_label = widgets.TextWidget(window, (410, 145), '', COLORS['text'], FONTS['main'], 14)

        self._track_sync = widgets.TextWidget(window, (32, 326), '', COLORS['midgrey'], FONTS['main'], 9)

        self._track_cover = None
        self.spectrum_analyzer = None  # set from main.py after AudioCapture is ready

        self._cover_frame = pygame.image.load(resource_path(COVER_FRAME))

        self._status = widgets.TextWidget(window, (350, 30), 'Please wait while updating track...',
                                          COLORS['alert_text'], FONTS['main'], 12)

        self._timer_display = widgets.TextWidget(window, (452, 299), '', COLORS['othergrey'], FONTS['main'], 15)

        self._timer = widgets.TrackTimer(0)

        self._progress_total_time = 0

        self.button_like = widgets.ButtonWidget(window, (351, 299),
                                                resource_path('assets/img/button_bookmark.png'),
                                                resource_path('assets/img/button_bookmark_active.png'))
        self.button_mute = widgets.ButtonWidget(window, (404, 299),
                                                resource_path('assets/img/button_mute.png'),
                                                resource_path('assets/img/button_mute_active.png'))
        self.button_settings = widgets.ButtonWidget(window, (864, 299),
                                                    resource_path('assets/img/button_settings.png'),
                                                    resource_path('assets/img/button_settings.png'))
        self.sep_line = ((160, 170, 170), (520, 299), (520, 316), 1)  # color, start_pos, end_pos, width
        self.txt_quality = widgets.TextWidget(window, (555, 301), self.text_quality, COLORS['othergrey'],
                                              FONTS['main'], 12)

        # Settings

        self.setting_connect = widgets.TextWidget(window, (85, 74), 'Connect to Spotify', COLORS['text_settings'],
                                                  FONTS['main_bold'], 14)
        self.setting_unique_playlist = widgets.TextWidget(window, (85, 109), 'Unique Spotify playlist: *',
                                                          COLORS['text_settings'], FONTS['main'], 14)

        self.setting_spotify_client_id_info = widgets.TextWidget(window, (440, 74), 'A Spotify client id is required to use Spotify playlist sync - see readme.',
                                                          COLORS['text_settings'], FONTS['main'], 11)

        self.setting_hifi = widgets.TextWidget(window, (60, 168), 'Hifi streaming: **',
                                               COLORS['text_settings'], FONTS['main'], 14)

        self.setting_dark = widgets.TextWidget(window, (60, 203), 'Dark mode',
                                               COLORS['text_settings'], FONTS['main'], 14)

        self.setting_footer_1 = widgets.TextWidget(window, (60, 238),
                                                   '* Default setting creates a separate playlist for each FIP '
                                                   'station. When toggled ON, a unique playlist will be used',
                                                   COLORS['text_settings'], FONTS['main'], 11)
        self.setting_footer_2 = widgets.TextWidget(window, (60, 253),
                                                   '** Default is Hifi AAC 192 kbps. Midfi is MP3 128 kbps.',
                                                   COLORS['text_settings'], FONTS['main'], 11)
        self.setting_footer_3 = widgets.TextWidget(window, (60, 278),
                                                   'Restart the player to apply changes.',
                                                   COLORS['alert_text'], FONTS['main'], 11)
        self.setting_about_link = widgets.LinkWidget(window, (255, 278),
                                                     'About Five spots player / licence',
                                                     COLORS['midblue'], FONTS['main'], 11, url='https://github.com/serialiser/five_spots_player#five-spots-player')
        self.setting_connect_button = widgets.ButtonWidget(window, (330, 69),
                                                           resource_path('assets/img/button_toggle_off.png'),
                                                           resource_path('assets/img/button_toggle_on.png'))
        self.setting_connect_button.active = settings.spotify_sync
        self.setting_unique_button = widgets.ButtonWidget(window, (330, 104),
                                                          resource_path('assets/img/button_toggle_off.png'),
                                                          resource_path('assets/img/button_toggle_on.png'))
        self.setting_unique_button.active = settings.unique_playlist
        self.setting_hifi_button = widgets.ButtonWidget(window, (190, 163),
                                                        resource_path('assets/img/button_toggle_off.png'),
                                                        resource_path('assets/img/button_toggle_on.png'))
        self.setting_hifi_button.active = settings.quality == 'hifi'
        self.setting_hifi_txt = widgets.TextWidget(window, (255, 168), '', COLORS['alert_text'], FONTS['main'], 11)
        self.setting_dark_button = widgets.ButtonWidget(window, (190, 198),
                                                        resource_path('assets/img/button_toggle_off.png'),
                                                        resource_path('assets/img/button_toggle_on.png'))
        self.setting_dark_button.active = settings.dark_mode
        self.setting_close_button = widgets.ButtonWidget(window, (WINDOW_WIDTH - 60, 30),
                                                         resource_path('assets/img/button_close.png'),
                                                         resource_path('assets/img/button_close.png'))

    @property
    def track_title(self):
        return self._track_title

    @property
    def track_artist(self):
        return self._track_artist

    @property
    def track_album(self):
        return self._track_album

    @property
    def track_label(self):
        return self._track_label

    @property
    def track_cover(self):
        return self._track_cover

    @property
    def cover_frame(self):
        return self._cover_frame

    @property
    def status(self):
        return self._status

    @property
    def labels(self):
        return self._labels

    @property
    def progress_total_time(self):
        return self._progress_total_time

    @property
    def timer(self):
        return self._timer

    @property
    def timer_display(self):
        return self._timer_display

    @property
    def track_sync(self):
        return self._track_sync

    async def update_cover(self, cover_url):
        """
        Loads cover img from url to pygame
        :return: None
        """
        if cover_url is None:
            self._track_cover = pygame.image.load(resource_path('assets/img/no-cover.png'))
            return
        try:
            connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url=cover_url) as response:
                    buffer = io.BytesIO(await response.read())
                    track_cover = pygame.image.load(buffer, 'cover.jpg')
                    track_cover = pygame.transform.smoothscale(track_cover, (290, 290))
        except Exception as e:
            logging.warning(f"Error loading cover img from {cover_url}: {e}", exc_info=True)
            track_cover = pygame.image.load(resource_path('assets/img/no-cover.png'))
        self._track_cover = track_cover

    def update_track(self, title, artist, album, year, label, end):
        album = f"{album} ({year})" if year else (album or '')
        self._track_artist.set_value(shorten_str(artist, 40))
        self._track_title.set_value(shorten_str(title, 70))
        self._track_album.set_value(shorten_str(album, 70))
        self._track_label.set_value(shorten_str(label, 70))

        self._progress_total_time = get_remaining_seconds(end)
        self._timer = widgets.TrackTimer(self._progress_total_time)
        self._timer.start()

    def update_sync(self, sync_status):
        self._track_sync.set_value(sync_status)

