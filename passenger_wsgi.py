"""
Passenger entry point for cPanel "Setup Python App" (Phusion Passenger).

cPanel points Passenger at this file. It loads the Django WSGI application
using the PRODUCTION settings module.

If cPanel generated its own passenger_wsgi.py when you created the Python App,
replace its contents with this file.
"""
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

# Make sure the project directory (this file's folder) is importable.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Use production settings unless overridden in the cPanel app's Environment Variables.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'journalpro.settings.production')

from journalpro.wsgi import application  # noqa: E402
