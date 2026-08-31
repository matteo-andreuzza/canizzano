#!/usr/bin/env python
"""Utility a riga di comando di Django per il CMS di canizzano.it."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "canizzano_cms.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django non risulta installato. Attiva il virtualenv "
            "oppure lancia il comando dentro il container."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
