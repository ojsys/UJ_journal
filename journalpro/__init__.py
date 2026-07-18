"""
Project package init.

Make PyMySQL masquerade as MySQLdb so Django's ``django.db.backends.mysql``
engine works without the compiled ``mysqlclient`` package. This is the reliable
MySQL driver on shared cPanel hosting, where mysqlclient can't build (no MySQL
dev headers / pkg-config).

PyMySQL reports version_info (1, 4, 6, ...), which satisfies Django's
"mysqlclient >= 1.4.3" check, so no extra shim is required.

Harmless when using SQLite/PostgreSQL: if PyMySQL isn't installed, we skip it.
"""
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:
    pass
