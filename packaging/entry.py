"""Launcher frozen by PyInstaller, which needs a script rather than a package to start from."""

import sys

from nodus.app import main

if __name__ == "__main__":
    sys.exit(main())
