# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Olivier Meyer

# Standard library
import sys
import os

# In frozen mode, work from the exe's directory so that .env, settings.json
# and data.json are resolved relative to it, not the temp extraction folder.
if hasattr(sys, '_MEIPASS'):
    os.chdir(os.path.dirname(sys.executable))

import asyncio
import time
import logging
import webbrowser

# Third party
import pygame

# Local imports
from utils import resource_path
from view.constants import WINDOW_WIDTH, WINDOW_HEIGHT, FRAMES_PER_SECOND, BGCOLOR, COLORS, BORDER_COLOR
from controller.controller import Controller, DropdownMenu
from view.widgets import TimeBar, SpectrumAnalyzer
from player_settings import PlayerSettings, spotify_connect, del_cache
from audio.capture import AudioCapture

logging.basicConfig(format='\n%(asctime)s - %(levelname)s: %(message)s', filename='app.log', encoding='utf-8',
                    level=logging.WARNING)

# We never use pygame.mixer for sound (audio goes through VLC + sounddevice).
# SDL otherwise opens an audio device at init, and on Linux that can hold the ALSA
# device exclusively and make PortAudio fail with "Device unavailable" (-9985).
# Tell SDL not to touch audio at all, before pygame.init().
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
pygame.init()
pygame.mixer.quit()  # belt-and-suspenders: release the mixer if it grabbed anything
window = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption(f'Five spots player')
icon = pygame.image.load(resource_path('assets/img/logo.png'))
pygame.display.set_icon(icon)
clock = pygame.time.Clock()

from model.fip_apis import API_AVAILABLE

capture = AudioCapture()
c = Controller(window, audio_capture=capture)
c.view.spectrum_analyzer = SpectrumAnalyzer(window, (350, 173), capture)
settings = PlayerSettings()

dropdown = DropdownMenu(c)
# Start on FIP automatically (no splash screen)
dropdown.activate_station('fip')


def main():
    elapsed_time = 0
    time_bar = TimeBar(window, (350, 268), (531, 5), COLORS['lightgrey'], COLORS['othergrey'])

    run = True
    while run:

        pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

        # Handle events
        event_list = pygame.event.get()
        for event in event_list:
            if event.type == pygame.QUIT:
                run = False

            # Play-screen buttons (only react while playing)
            if c.state == 'play':
                if c.view.button_like.handle_event(event):
                    track = c.tracks.get_or_create_track(c.current_station)
                    track.bookmark()
                    c.view.update_sync(track.sync_msg)

                if c.view.button_mute.handle_event(event):
                    c.play_or_pause()

                if c.view.button_settings.handle_event(event):
                    c.set_state('settings')
                    dropdown.close()

            # Settings-screen buttons (only react while in settings)
            elif c.state == 'settings':
                if c.view.setting_close_button.handle_event(event):
                    c.set_state('play')

                if settings.spotify_sync is False:
                    c.view.setting_connect_button.active = False
                    if c.view.setting_connect_button.handle_event(event):
                        spot_client, spot_user = spotify_connect()
                        if spot_user:
                            settings.set_spotify_sync(True)
                elif settings.spotify_sync is True:
                    if c.view.setting_connect_button.handle_event(event):
                        settings.set_spotify_sync(False)
                        del_cache()

                if settings.unique_playlist is False:
                    if c.view.setting_unique_button.handle_event(event):
                        settings.set_unique_playlist(True)
                elif settings.unique_playlist is True:
                    if c.view.setting_unique_button.handle_event(event):
                        settings.set_unique_playlist(False)

                if settings.quality == 'midfi':
                    if c.view.setting_hifi_button.handle_event(event):
                        settings.set_quality('hifi')
                elif settings.quality == 'hifi':
                    if c.view.setting_hifi_button.handle_event(event):
                        settings.set_quality('midfi')

                if settings.dark_mode is False:
                    if c.view.setting_dark_button.handle_event(event):
                        settings.set_dark_mode(True)
                elif settings.dark_mode is True:
                    if c.view.setting_dark_button.handle_event(event):
                        settings.set_dark_mode(False)

                if c.view.setting_about_link.handle_event(event):
                    url = c.view.setting_about_link.url
                    if url and url != '#':
                        webbrowser.open(url)

        # Per frame actions
        if c.state != 'settings':
            dropdown.update(event_list)

        if c.state == 'play':
            c.view.button_like.update_hover()
            c.view.button_mute.update_hover()
            c.view.button_settings.update_hover()

        if c.state == 'settings':
            c.view.setting_close_button.update_hover()
            c.view.setting_about_link.update_hover()
            c.view.setting_connect_button.update_hover()
            c.view.setting_unique_button.update_hover()
            c.view.setting_hifi_button.update_hover()
            c.view.setting_dark_button.update_hover()

        remaining_time = c.view.timer.get_remaining_time()
        c.view.timer_display.set_value(remaining_time)

        # Draw all window elements
        window.fill(BGCOLOR)

        # Play screen
        if c.state == 'play':

            track = c.tracks.get_or_create_track(c.current_station)

            needs_update = API_AVAILABLE and not track.is_current()
            if needs_update and not track.is_blank:
                # Update track infos
                c.view.status.draw()
                c.view.timer.stop()
                # Wait a little before requesting API to get proper data
                if track.end:
                    delay = time.time() - track.end
                    if delay > 5:
                        asyncio.run(c.update_track(track))
                else:
                    asyncio.run(c.update_track(track))
            elif needs_update and track.is_blank:
                # Retry if blank (no data between tracks), rate-limited to every 10s
                if time.time() - track._last_update_attempt > 10:
                    c.view.timer.stop()
                    asyncio.run(c.update_track(track))

            # Draw track infos and cover
            for i in c.view.labels:
                i.draw()
            c.view.track_title.draw()
            c.view.track_artist.draw()
            c.view.track_album.draw()
            c.view.track_label.draw()
            if c.view.track_cover:
                window.blit(c.view.track_cover, (30, 30))
                window.blit(c.view.cover_frame, (30, 30))
                pygame.draw.rect(window, BORDER_COLOR, (30, 30, 290, 290), 3, border_radius=10)
            c.view.track_sync.draw()

            # Spectrum analyzer
            if c.view.spectrum_analyzer:
                c.view.spectrum_analyzer.update()
                c.view.spectrum_analyzer.draw()

            # Remaining time
            c.view.timer_display.draw()

            # Progress bar
            total_time = c.view.progress_total_time
            progress = elapsed_time / total_time if total_time > 0 else 1
            time_bar.draw(progress)
            elapsed_time = c.view.progress_total_time - c.view.timer.get_remaining_seconds()
            if elapsed_time >= total_time:
                elapsed_time = total_time

            # Buttons
            if track.bookmarked is False:
                c.view.button_like.active = False
            else:
                c.view.button_like.active = True
            c.view.button_like.draw()
            c.view.button_mute.draw()
            c.view.button_settings.draw()
            c.view.txt_quality.draw()
            # Separation line
            l_color, l_start, l_end, l_width = c.view.sep_line
            pygame.draw.line(window, l_color, l_start, l_end, l_width)

        # Settings screen
        elif c.state == 'settings':
            # Background
            pygame.draw.rect(window, BGCOLOR, pygame.Rect(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT))
            pygame.draw.rect(window, COLORS['verylightgrey'], pygame.Rect(20, 20, 871, 310), 0, 8)
            pygame.draw.rect(window, COLORS['lightgrey'], pygame.Rect(60, 49, 350, 100), 0, 8)

            c.view.setting_close_button.draw()
            c.view.setting_connect.draw()
            c.view.setting_spotify_client_id_info.draw()
            c.view.setting_unique_playlist.draw()
            c.view.setting_hifi.draw()
            c.view.setting_dark.draw()
            c.view.setting_footer_1.draw()
            c.view.setting_footer_2.draw()
            c.view.setting_footer_3.draw()
            c.view.setting_about_link.draw()
            c.view.setting_connect_button.draw()
            c.view.setting_unique_button.draw()
            c.view.setting_hifi_button.draw()
            c.view.setting_hifi_txt.draw()
            c.view.setting_dark_button.draw()

        # Dropdown drawn last so it overlays content
        if c.state != 'settings':
            dropdown.draw(window)

        # Update the window
        pygame.display.flip()

        # Make pygame wait
        clock.tick(FRAMES_PER_SECOND)


if __name__ == '__main__':
    main()
    capture.close()
    pygame.quit()
    sys.exit()
