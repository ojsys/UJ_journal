#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

# Shared hosting caps the number of processes/threads a user may spawn, and
# OpenBLAS (pulled in via numpy -> yake) tries to start one thread per CPU core.
# That fails noisily and can hang the import, so pin the math libraries to a
# single thread. Must run before numpy is imported anywhere.
for _var in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_var, "1")


def main():
    """Run administrative tasks."""
    # Default to development settings for local development
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'journalpro.settings.development')
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
