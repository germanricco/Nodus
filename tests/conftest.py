"""Shared test setup."""

import os

# Render Qt widgets without a visible window, so tests run headless and in CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
