# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Olivier Meyer

# Standard library
import asyncio
import re
import time
import datetime
import json
import logging
from pathlib import Path

# Third party
import aiohttp

# Local imports
from model.fip_apis import WEBRADIOS, WEBRADIO_PLAYLIST_NAMES, GRAPHQL_API_URL, query_body
from player_settings import PlayerSettings, spotify_connect, USER_PLAYLIST_DEFAULT_NAME, USER_PLAYLIST_PREFIX

BOOKMARKS = Path('data.json')
NOT_FOUND = Path('notfound.csv')


settings = PlayerSettings()
if settings.spotify_sync is True:
    sp, spotify_user_id = spotify_connect()
else:
    sp, spotify_user_id = None, None


class Tracks:
    """
    Manages Track instances. Only one track instance for each station.
    """

    def __init__(self):
        self._tracks = dict()

    def get_or_create_track(self, station):
        """
        Get the track or creates one if it not exists.
        :param station: (str), name of station, e.g. 'jazz'
        :return: track
        """
        if station in self._tracks:
            return self._tracks[station]
        else:
            track = self._create_track(station)
            return track

    def _create_track(self, station):
        track = Track(station)
        self._tracks[station] = track
        return track

    @staticmethod
    def load_bookmarks():
        if BOOKMARKS.exists():
            with open(BOOKMARKS, "r", encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.decoder.JSONDecodeError as e:
                    data = None
                    logging.error(f"Error in loading bookmark: {e}", exc_info=True)
            return data

    @staticmethod
    def write_bookmark(data):
        with open(BOOKMARKS, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)


class Track:
    """
    A track instance holds the current track data for one station.
    There should'nt be more track instances than stations.
    """

    def __init__(self, radio):
        """
        Init an empty track to be updated with api call.
        Created by the object manager (class Tracks).
        self._artists: list
        self.artists getter: string ("artist1, artist2,...")
        """
        self._radio = WEBRADIOS[radio] if radio else None
        self._step_id = None
        self._start, self._end = None, None
        self._track_id = None
        self._title = None
        self._album = None
        self._year = None
        self._artists = []
        self._label = None
        self._cover_url = None
        self._current = self.is_current()
        self._is_blank = False
        self._last_update_attempt = 0
        self.bookmarked = self.is_bookmarked()
        self.sync_msg = ""
        self.spotify_song = Song(self)
        self.bookmark_clicks_count = 0

    def is_bookmarked(self):
        """
        Check if a track is bookmarked in the JSON file.
        :return: True/False
        """
        bookmarks = Tracks.load_bookmarks()
        if bookmarks:
            if self._track_id in bookmarks:
                return True
            else:
                return False
        return False

    @property
    def artists(self):
        if self._artists:
            artists = ", ".join(self._artists)
        else:
            artists = None
        return artists

    @property
    def track_id(self):
        return self._track_id

    @property
    def radio(self):
        return self._radio

    @property
    def title(self):
        return self._title

    @property
    def album(self):
        return self._album

    @property
    def year(self):
        return self._year

    @property
    def label(self):
        return self._label

    @property
    def end(self):
        return self._end

    @property
    def cover_url(self):
        return self._cover_url

    @property
    def is_blank(self):
        return self._is_blank

    def is_current(self):
        current_time = int(time.time())
        if not self._start:
            return False
        elif self._start < current_time < self._end:
            return True
        else:
            return False

    @staticmethod
    async def _fetch_graphql(radio, session):
        q = query_body(radio)
        async with session.post(GRAPHQL_API_URL, json={"query": q}) as response:
            if response.status == 200:
                content = await response.json(content_type=None)
                try:
                    song = content['data']['live']['song']
                    if song and song.get('track') and song['track'].get('id'):
                        return song
                except (KeyError, TypeError):
                    pass
                return None
            else:
                logging.critical(f'GraphQL error: {response.status}')
                return None

    async def query_data(self):
        """
        GraphQL API call to get track infos. Updates track instance.
        """
        self.sync_msg = ""
        self._last_update_attempt = time.time()

        if not GRAPHQL_API_URL:
            # Degraded mode: no Radio France API token. Audio still plays butno metadata is available.
            self._start = self._end = self._track_id = None
            self._label = self._year = None
            self._artists = ["[Fallback mode]"]
            self._title = "Radiofrance API Key needed"
            self._album = "See readme.txt"
            self._is_blank = True
            return

        nb_retry = 3
        delay_before_retry = 1
        data = None

        async with aiohttp.ClientSession() as session:
            nb_checks = 0
            while data is None and nb_checks <= nb_retry:
                data = await self._fetch_graphql(self._radio, session)
                nb_checks += 1
                if data is None and nb_checks <= nb_retry:
                    await asyncio.sleep(delay_before_retry)

            if data:
                try:
                    self._start, self._end = data['start'], data['end']
                except (KeyError, TypeError) as e:
                    self._start, self._end = None, None
                    logging.error(f"Error in start/end: {e}", exc_info=True)
                try:
                    self._track_id = data['track']['id']
                except (KeyError, TypeError) as e:
                    self._track_id = None
                    logging.error(f"Error in track_id: {e}", exc_info=True)
                try:
                    self._title = data['track']['title']
                except (KeyError, TypeError) as e:
                    self._title = None
                    logging.error(f"Error in title: {e}", exc_info=True)
                try:
                    self._album = data['track']['albumTitle']
                except (KeyError, TypeError) as e:
                    self._album = None
                    logging.error(f"Error in album: {e}", exc_info=True)
                try:
                    self._artists = data['track']['mainArtists']
                except (KeyError, TypeError) as e:
                    self._artists = []
                    logging.error(f"Error in artists: {e}", exc_info=True)
                try:
                    self._label = data['track'].get('label')
                except (KeyError, TypeError) as e:
                    self._label = None
                    logging.error(f"Error in label: {e}", exc_info=True)
                self._year = None  # not in GraphQL schema

                self._is_blank = False
                self.bookmarked = self.is_bookmarked()
                self._current = self.is_current()

                if self.spotify_song and self.spotify_song.track_id != self.track_id:
                    self._cover_url = None
                    self.spotify_song = Song(self)

            else:
                self._start = self._end = self._track_id = self._title = self._album = self._label = None
                self._artists = []
                self._is_blank = True

    async def query_cover(self):
        if not GRAPHQL_API_URL:
            # No metadata in degraded mode, so no cover to look up.
            self._cover_url = None
            return
        if settings.spotify_sync and self.spotify_song and self.spotify_song.title:
            url = self.spotify_song.get_spotify_cover_url()
            if url:
                self._cover_url = url
                return
        url = await self._fetch_deezer_cover()
        if url:
            self._cover_url = url
            return
        self._cover_url = await self._fetch_itunes_cover()

    async def _fetch_deezer_cover(self):
        if not self._title:
            return None
        searches = []
        if self._artists:
            searches.append(f"{self._title} {self.artists}")
        searches.append(self._title)
        async with aiohttp.ClientSession() as session:
            for term in searches:
                try:
                    params = {'q': term, 'limit': 5}
                    async with session.get('https://api.deezer.com/search', params=params) as r:
                        if r.status == 200:
                            data = await r.json(content_type=None)
                            for item in data.get('data', []):
                                album = item.get('album') or {}
                                cover = album.get('cover_xl') or album.get('cover_big') or album.get('cover')
                                if cover:
                                    return cover
                        else:
                            logging.warning(f"Deezer cover: HTTP {r.status} for '{term}'")
                except Exception as e:
                    logging.warning(f"Deezer cover fetch error for '{term}': {e}", exc_info=True)
        return None

    async def _fetch_itunes_cover(self):
        if not self._title:
            return None
        searches = []
        if self._artists:
            searches.append(f"{self._title} {self.artists}")
        searches.append(self._title)
        async with aiohttp.ClientSession() as session:
            for term in searches:
                try:
                    params = {'term': term, 'media': 'music', 'entity': 'song', 'limit': 5}
                    async with session.get('https://itunes.apple.com/search', params=params) as r:
                        if r.status == 200:
                            data = await r.json(content_type=None)
                            for item in data.get('results', []):
                                artwork = item.get('artworkUrl100')
                                if artwork:
                                    return re.sub(r'\d+x\d+bb', '600x600bb', artwork)
                        else:
                            logging.warning(f"iTunes cover: HTTP {r.status} for '{term}'")
                except Exception as e:
                    logging.warning(f"iTunes cover fetch error for '{term}': {e}", exc_info=True)
        return None

    def is_cover_updated(self):
        return self._cover_url is not None

    def get_track_data(self, artists_format="list"):
        """
        :param artists_format: method will return a list by default, else string ("artist1, artist2,...")
        :return: track data (dict)
        """
        if artists_format == "list":
            artists = self._artists
        else:
            artists = self.artists
        return {
            f"{self._track_id}": {"radio": self._radio, "start": self._start, "end": self._end, "title": self._title,
                                  "artists": artists, "album_title": self._album}}

    def not_found_in_spotify(self):
        """
        If a song is not found via spotify API, it's written in a separate file.
        :return: None
        """
        with open(NOT_FOUND, "a+") as f:
            f.write(f"{self.artists}; {self.album}; {self.title}\n")

    def bookmark(self):
        """
        Adds/removes current track to/from bookmarks file and updates object bookmarked attribute.
        Adds/removes song to/from spotify playlist.
        A TRACK KEEPS HIS BOOKMARKED STATE SAVED IN FILE, WHEREAS SPOTIFY SYNC IS JUST KEPT IN-MEMORY IN SONG OBJECT.
        :return: None
        """

        if not self.is_blank:
            track_data = self.get_track_data()
            bookmarks = Tracks.load_bookmarks()

            playlist = self.set_playlist_name()

            # Spotify sync - cases when clicking the like button (bookmark())
            # When reopening the player
            if sp and self.bookmark_clicks_count == 0 and self.bookmarked is True:
                pass
            # Case not found in spotify
            elif sp and self.spotify_song.found is False and self.bookmarked is False:
                # Current track was previously searched for
                self.spotify_song.set_msg("Not found in Spotify.")

            # Case not found in spotify and bookmarked, clear message
            elif sp and self.spotify_song.found is False and self.bookmarked is True:
                self.spotify_song.set_msg("")
            # Try to add song to spotify playlist
            elif sp and self.spotify_song.playlist is None:
                if self.spotify_song.add_to_spotify_playlist(playlist):
                    self.spotify_song.playlist = playlist
                else:
                    self.not_found_in_spotify()

            # Try to remove song from spotify playlist
            elif sp and self.spotify_song.playlist is not None:
                if self.spotify_song.remove_from_spotify_playlist():
                    self.spotify_song.playlist = None

            self.sync_msg = self.spotify_song.sync_msg

            # Add to / remove from bookmarks
            if bookmarks:
                if not self.is_bookmarked():
                    try:
                        bookmarks[self._track_id] = track_data[self._track_id]
                        self.bookmarked = True
                    except KeyError as e:
                        logging.error(f"KeyError in bookmarks: {e}", exc_info=True)
                else:
                    # delete bookmark
                    bookmarks.pop(self._track_id)
                    self.bookmarked = False
                Tracks.write_bookmark(bookmarks)
            else:
                # Initialize json
                Tracks.write_bookmark(track_data)
                self.bookmarked = True

            # Without Spotify sync there is no sync message, so report the
            # bookmark action itself based on the resulting state.
            if not sp:
                self.sync_msg = "Track added to bookmarks" if self.bookmarked \
                    else "Track removed from bookmarks"

            self.bookmark_clicks_count += 1

    def set_playlist_name(self):
        if settings.unique_playlist:
            playlist = USER_PLAYLIST_DEFAULT_NAME
        else:
            suffix = WEBRADIO_PLAYLIST_NAMES.get(self._radio, self._radio.split('_')[-1].lower())
            playlist = USER_PLAYLIST_PREFIX + ' - ' + suffix
        return playlist


class Song:
    """
    Contains track data to search for in spotify catalog, and then to synchronize with Spotify playlist.
    Created when a track instance is created.
    To be updated when a track instance is updated.
    """

    def __init__(self, track):
        """
        :param track: Track instance
        """
        self.track = track
        self.title = self.track.title
        self.artist = self.track.artists
        self.album = self.track.album
        self.track_id = self.track.track_id
        self.spotify_track_id = None
        self._sync_msg = ""
        self.playlist = None
        self._found = None

    @property
    def sync_msg(self):
        return self._sync_msg

    def set_msg(self, msg):
        self._sync_msg = msg

    def get_spotify_cover_url(self):
        if not sp or not self.title:
            return None
        try:
            for search_args in [
                (self.title, self.artist, self.album),
                (self.title, self.artist),
                (self.title, self.album),
            ]:
                results = self._search(*search_args)
                items = results.get('tracks', {}).get('items', [])
                if items:
                    images = items[0].get('album', {}).get('images', [])
                    if images:
                        return images[0]['url']  # largest first (640px)
        except Exception as e:
            logging.error(f"Error fetching Spotify cover: {e}", exc_info=True)
        return None

    @property
    def found(self):
        """
        :return: None if never searched for, False if not found
        """
        return self._found

    def add_to_spotify_playlist(self, playlist):
        """
        Search for a track and if found, adds it to playlist
        :param playlist: name (str), depending on config: global (Five spots player),
        or one per station (Five spots player jazz, ...)
        :return: True, None if failed
        """

        # Search for song in Spotify catalog
        results = self._search(self.title, self.artist, self.album)
        if len(results['tracks']['items']) == 0:
            logging.info(f"No results for {self.title}, {self.artist}, {self.album}")
            # Refine search
            results = self._search(self.title, self.artist)
            if len(results['tracks']['items']) == 0:
                logging.info(f"No results for {self.title}, {self.artist}")
                results = self._search(self.title, self.album)
                if len(results['tracks']['items']) == 0:
                    logging.info(f"No results for {self.title}, {self.album}")
                    self._sync_msg = "Could'nt add to Spotify."
                    self._found = False

        if len(results['tracks']['items']) > 0:
            logging.info(f"Matching title found for {self.title}")
            # there is a matching track
            playlist_id = self.get_or_create_playlist(playlist)
            self.spotify_track_id = results['tracks']['items'][0]['id']

            # Add to playlist only if not already exists
            playlist_tracks_id = self.get_tracks_id_from_playlist(playlist_id)
            if self.spotify_track_id not in playlist_tracks_id:
                sp.playlist_add_items(playlist_id, [self.spotify_track_id])
                self._sync_msg = "Track added to Spotify playlist."
            else:
                self._sync_msg = "This track is already in Spotify playlist."
            return True

    def remove_from_spotify_playlist(self):
        if self.playlist is not None:
            playlist_id = self.get_or_create_playlist(self.playlist)
            sp.playlist_remove_all_occurrences_of_items(playlist_id, [self.spotify_track_id])
            self._sync_msg = "Track removed from Spotify playlist."
            return True

    @staticmethod
    def _search(title, artist=None, album=None):
        """
        Search for a song in spotify catalog.
        Either artist or album must not be empty
        :param title: Required (str)
        :param artist: artist name, or artists names (comma separated) (str)
        :param album: album (str)
        :return: result (dict)
        """
        # cleaning
        title = Song.replace_quotes(title)
        if artist:
            artist = Song.replace_quotes(artist)
            artist = artist.replace(' & ', ', ')  # artist1, artist2...
        album = Song.replace_quotes(album) if album else None

        if not album:
            results = sp.search(q=f'track:{title} artist:{artist}', limit=1, type='track', market='FR')
        elif not artist:
            results = sp.search(q=f'track:{title} album:{album}', limit=1, type='track', market='FR')
        else:
            results = sp.search(q=f'track:{title} artist:{artist} album:{album}', limit=1, type='track', market='FR')
        return results

    @staticmethod
    def get_tracks_id_from_playlist(playlist_id):
        results = sp.playlist_items(playlist_id, fields="items(track(id))")
        tracks_ids = [i['track']['id'] for i in results['items']]
        return tracks_ids

    @staticmethod
    def get_or_create_playlist(name):
        """
        Get a playlist id if it exists
        :param name: name of the playlist
        :return: playlist id / None if failed
        """
        playlists = sp.current_user_playlists()

        if playlists:
            try:
                playlists_names = [playlist['name'] for playlist in playlists['items']]
            except TypeError as e:
                logging.error(f"TypeError in get_or_create_playlist: {e}", exc_info=True)
                playlists_names = []

            if name not in playlists_names:
                # Create playlist
                today = datetime.date.today().strftime("%B %d, %Y")
                playlist = sp.user_playlist_create(spotify_user_id, name, public=False, collaborative=False,
                                                   description=f"Created by Five spots player on {today}")
                return playlist['id']
            else:
                # Get playlist
                for playlist in (playlists['items']):
                    if playlist['name'] == name:
                        return playlist['id']

    @staticmethod
    def replace_quotes(s):
        return s.replace("'", r"\'").replace('"', r'\"')
