#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # Windows terminals often default stdout/stderr to a legacy codepage
    # (cp1252 / "charmap") that can't encode Unicode punctuation used
    # elsewhere in this project (✓, →, em dashes, Σ, etc.) — this crashes
    # Django's console email backend (and any print()) the moment such a
    # character appears, with "UnicodeEncodeError: 'charmap' codec can't
    # encode character...". Reconfiguring to UTF-8 here fixes it for every
    # management command (runserver, send_analytics_alerts, ...), not just
    # one code path, and is a no-op on platforms already using UTF-8.
    for stream in (sys.stdout, sys.stderr):
        encoding = getattr(stream, 'encoding', None)
        if encoding and encoding.lower() != 'utf-8':
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, ValueError):
                pass  # stream doesn't support reconfigure (e.g. redirected to a non-text target) — safe to skip

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mathapi.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
