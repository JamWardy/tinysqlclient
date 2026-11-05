"""PEP 249's exceptions, chosen by SQLSTATE class as psycopg does."""


class Warning(Exception):
    pass


class Error(Exception):
    def __init__(self, message, sqlstate=None):
        super().__init__(message)
        self.sqlstate = sqlstate


class InterfaceError(Error):
    pass


class DatabaseError(Error):
    pass


class DataError(DatabaseError):
    pass


class OperationalError(DatabaseError):
    pass


class IntegrityError(DatabaseError):
    pass


class InternalError(DatabaseError):
    pass


class ProgrammingError(DatabaseError):
    pass


class NotSupportedError(DatabaseError):
    pass


_BY_CLASS = {
    "22": DataError,
    "23": IntegrityError,
    "42": ProgrammingError,
    "0A": NotSupportedError,
    "08": OperationalError,
    "25": OperationalError,
    "53": OperationalError,
    "54": OperationalError,
    "55": OperationalError,
    "58": OperationalError,
    "XX": InternalError,
}


def error_for(sqlstate, message):
    """The exception for an error the server sent."""
    cls = _BY_CLASS.get(sqlstate[:2], DatabaseError)
    return cls(message, sqlstate)
