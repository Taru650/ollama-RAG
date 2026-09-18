"""Force UTF-8 console I/O before any script prints Hindi text.

Windows terminals frequently don't default sys.stdout/stderr to UTF-8
(legacy code page instead), which raises UnicodeEncodeError the
instant a script tries to print Devanagari -- not a hypothetical edge
case for this project, since printing Hindi text is the core job of
every CLI script here. reconfigure() is a no-op in effect on
Linux/macOS, where stdout is already UTF-8, so this is safe to call
unconditionally on every platform.
"""
from __future__ import annotations

import sys


def ensure_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass  # best-effort -- e.g. a stream that doesn't support it
