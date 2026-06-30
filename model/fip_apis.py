from decouple import config

_token = config('RADIOFRANCE_API_TOKEN', default=None) or None
GRAPHQL_API_URL = f"https://openapi.radiofrance.fr/v1/graphql?x-token={_token}" if _token else None

# When no Radio France API token is configured, the app runs in degraded mode:
# audio streams still play, but track metadata can't be fetched.
API_AVAILABLE = GRAPHQL_API_URL is not None

# webradios names
WEBRADIOS = {'fip': 'FIP', 'rock': 'FIP_ROCK', 'jazz': 'FIP_JAZZ', 'groove': 'FIP_GROOVE', 'world': 'FIP_WORLD',
             'new': 'FIP_NOUVEAUTES', 'reggae': 'FIP_REGGAE', 'electro': 'FIP_ELECTRO', 'metal': 'FIP_METAL',
             'pop': 'FIP_POP', 'hiphop': 'FIP_HIP_HOP', 'sacrefrancais': 'FIP_SACREFRANCAIS',
             'cultes': 'FIP_CULTES'}

# Suffix used to name the per-station Spotify playlist ("<prefix> - <suffix>").
# Mapped explicitly per station enum instead of slicing the enum string: multi-word
# enums like FIP_HIP_HOP would otherwise collapse to a meaningless suffix ("hop").
# The first 10 values reproduce the historical suffix so existing user playlists keep
# being matched; only the 3 newest stations get a fresh, correct name.
WEBRADIO_PLAYLIST_NAMES = {'FIP': 'fip', 'FIP_ROCK': 'rock', 'FIP_JAZZ': 'jazz', 'FIP_GROOVE': 'groove',
                           'FIP_WORLD': 'world', 'FIP_NOUVEAUTES': 'nouveautes', 'FIP_REGGAE': 'reggae',
                           'FIP_ELECTRO': 'electro', 'FIP_METAL': 'metal', 'FIP_POP': 'pop',
                           'FIP_HIP_HOP': 'hip-hop', 'FIP_SACREFRANCAIS': 'sacre francais',
                           'FIP_CULTES': 'cultes'}


def query_body(radio):
    q = """
    {
      live(station: """ + radio + """) {
        song {
          id
          start
          end
          track {
            id
            title
            albumTitle
            mainArtists
            label
          }
        }
      }
    }
    """
    return q
