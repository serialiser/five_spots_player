from decouple import config

_token = config('RADIOFRANCE_API_TOKEN', default=None) or None
GRAPHQL_API_URL = f"https://openapi.radiofrance.fr/v1/graphql?x-token={_token}" if _token else None

# When no Radio France API token is configured, the app runs in degraded mode:
# audio streams still play, but track metadata can't be fetched.
API_AVAILABLE = GRAPHQL_API_URL is not None

# webradios names
WEBRADIOS = {'fip': 'FIP', 'rock': 'FIP_ROCK', 'jazz': 'FIP_JAZZ', 'groove': 'FIP_GROOVE', 'world': 'FIP_WORLD',
             'new': 'FIP_NOUVEAUTES', 'reggae': 'FIP_REGGAE', 'electro': 'FIP_ELECTRO', 'metal': 'FIP_METAL',
             'pop': 'FIP_POP'}


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
