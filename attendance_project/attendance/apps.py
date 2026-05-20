from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    name = "attendance"

    def ready(self):
        from django.db.backends.signals import connection_created

        def _set_sqlite_pragmas(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                cursor = connection.cursor()
                cursor.execute('PRAGMA journal_mode=WAL;')      # concurrent readers + 1 writer
                cursor.execute('PRAGMA synchronous=NORMAL;')    # fast + safe
                cursor.execute('PRAGMA cache_size=10000;')
                cursor.execute('PRAGMA temp_store=MEMORY;')
                cursor.execute('PRAGMA busy_timeout=30000;')    # wait 30s instead of "database locked"

        connection_created.connect(_set_sqlite_pragmas)
