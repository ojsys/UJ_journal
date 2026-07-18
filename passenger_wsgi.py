"""
Passenger entry point for cPanel "Setup Python App" (Phusion Passenger).

cPanel points Passenger at this file. It loads the Django WSGI application
using the PRODUCTION settings module.

If cPanel generated its own passenger_wsgi.py when you created the Python App,
replace its contents with this file.
"""
import os
import sys

# Make sure the project directory (this file's folder) is importable.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Use production settings unless overridden in the cPanel app's Environment Variables.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'journalpro.settings.production')

from journalpro.wsgi import application  # noqa: E402
