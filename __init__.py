"""A client for TinySQL's server, as psycopg is for Postgres. See DESIGN.md."""

from .connection import Connection, Cursor
from .errors import (DatabaseError, DataError, Error, IntegrityError,
                     InterfaceError, InternalError, NotSupportedError,
                     OperationalError, ProgrammingError, Warning)
from .protocol import BOOL, INT, NULL, TEXT

apilevel = "2.0"
# Threads may share the module, not a connection.
threadsafety = 1
paramstyle = "qmark"


def connect(host="127.0.0.1", port=5480):
    return Connection(host, port)
