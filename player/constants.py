# Network buffering depth (ms) applied identically to the main player and the
# silent capture player. Matching the value keeps their buffering aligned so the
# spectrum analyzer stays close to what is heard. Lower = tighter sync and less
# latency, but more prone to dropouts on a poor connection (VLC default: 1000).
NETWORK_CACHING_MS = 500

# webradios urls midfi (mp3)
STREAM_URLS_MP3 = dict()
STREAM_URLS_MP3['fip'] = 'http://icecast.radiofrance.fr/fip-midfi.mp3'
STREAM_URLS_MP3['rock'] = 'http://icecast.radiofrance.fr/fiprock-midfi.mp3'
STREAM_URLS_MP3['jazz'] = 'http://icecast.radiofrance.fr/fipjazz-midfi.mp3'
STREAM_URLS_MP3['groove'] = 'http://icecast.radiofrance.fr/fipgroove-midfi.mp3'
STREAM_URLS_MP3['world'] = 'http://icecast.radiofrance.fr/fipworld-midfi.mp3'
STREAM_URLS_MP3['new'] = 'http://icecast.radiofrance.fr/fipnouveautes-midfi.mp3'
STREAM_URLS_MP3['reggae'] = 'http://icecast.radiofrance.fr/fipreggae-midfi.mp3'
STREAM_URLS_MP3['electro'] = 'http://icecast.radiofrance.fr/fipelectro-midfi.mp3'
STREAM_URLS_MP3['metal'] = 'http://icecast.radiofrance.fr/fipmetal-midfi.mp3'
STREAM_URLS_MP3['pop'] = 'http://icecast.radiofrance.fr/fippop-midfi.mp3'

# webradios urls hifi (aac)
STREAM_URLS_AAC = dict()
STREAM_URLS_AAC['fip'] = 'http://icecast.radiofrance.fr/fip-hifi.aac'
STREAM_URLS_AAC['rock'] = 'http://icecast.radiofrance.fr/fiprock-hifi.aac'
STREAM_URLS_AAC['jazz'] = 'http://icecast.radiofrance.fr/fipjazz-hifi.aac'
STREAM_URLS_AAC['groove'] = 'http://icecast.radiofrance.fr/fipgroove-hifi.aac'
STREAM_URLS_AAC['world'] = 'http://icecast.radiofrance.fr/fipworld-hifi.aac'
STREAM_URLS_AAC['new'] = 'http://icecast.radiofrance.fr/fipnouveautes-hifi.aac'
STREAM_URLS_AAC['reggae'] = 'http://icecast.radiofrance.fr/fipreggae-hifi.aac'
STREAM_URLS_AAC['electro'] = 'http://icecast.radiofrance.fr/fipelectro-hifi.aac'
STREAM_URLS_AAC['metal'] = 'http://icecast.radiofrance.fr/fipmetal-hifi.aac'
STREAM_URLS_AAC['pop'] = 'http://icecast.radiofrance.fr/fippop-hifi.aac'
