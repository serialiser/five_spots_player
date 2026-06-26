from utils import resource_path
from player_settings import PlayerSettings

WINDOW_WIDTH = 911
WINDOW_HEIGHT = 350
FRAMES_PER_SECOND = 60
FONTS = {'main': resource_path('assets/fonts/Roboto-Light.ttf'),
         'title': resource_path('assets/fonts/Merriweather-Bold.ttf'),
         'main_bold': resource_path('assets/fonts/Roboto-Bold.ttf')}

# Light theme (cover-frame.png rounded corners are tuned for the light background).
LIGHT_BGCOLOR = (250, 250, 250)
LIGHT_COLORS = {'bgcolor': (250, 250, 250), 'verylightgrey': (236, 240, 241), 'lightgrey': (207, 211, 214),
                'midgrey': (149, 165, 166), 'othergrey': (127, 140, 141), 'heavyblue': (41, 128, 185),
                'midblue': (52, 152, 219), 'textbutton': (255, 255, 255), 'text': (52, 73, 94),
                'alert_text': (211, 84, 0), 'text_settings': (85, 85, 85), 'darkblue': (52, 73, 94)}

# Dark theme (cover-frame-dark.png rounded corners are tuned for the dark background).
DARK_BGCOLOR = (40, 44, 52)
DARK_COLORS = {'bgcolor': (50, 54, 62), 'verylightgrey': (50, 54, 62), 'lightgrey': (37, 37, 38),
               'midgrey': (156, 163, 175), 'othergrey': (156, 163, 175), 'heavyblue': (52, 152, 219),
               'midblue': (52, 152, 219), 'textbutton': (255, 255, 255), 'text': (212, 212, 212),
               'alert_text': (235, 130, 55), 'text_settings': (212, 212, 212), 'darkblue': (212, 212, 212)}

DARK_MODE = PlayerSettings().dark_mode

if DARK_MODE:
    COLORS = DARK_COLORS
    BGCOLOR = DARK_BGCOLOR
    COVER_FRAME = 'assets/img/cover-frame-dark.png'
    BORDER_COLOR = (59, 64, 76)
else:
    COLORS = LIGHT_COLORS
    BGCOLOR = LIGHT_BGCOLOR
    COVER_FRAME = 'assets/img/cover-frame.png'
    BORDER_COLOR = LIGHT_COLORS['lightgrey']
