import os
import sys

# Add _internal (sys._MEIPASS) to PATH so Windows finds DLLs loaded dynamically
# by SDL2_image (libpng, libjpeg, etc.) via plain LoadLibrary.
if hasattr(sys, '_MEIPASS'):
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')
