"""TinySQL's messages to and from bytes, as ../tinysql/src/server/protocol.h
defines them. No socket here."""

import struct

from .errors import DataError

HEADER = struct.Struct(">cI")

QUERY = b"Q"
TERMINATE = b"X"
COLUMNS = b"T"
ROW = b"D"
COMPLETE = b"C"
ERROR = b"E"
READY = b"Z"

NULL = 0
INT = 1
TEXT = 2
BOOL = 3

_INT_MIN = -(1 << 63)
_INT_MAX = (1 << 63) - 1


def _message(type, body):
    return HEADER.pack(type, len(body)) + body


def _encode_value(value):
    if value is None:
        return bytes([NULL])
    # Before int, as True is an int too.
    if isinstance(value, bool):
        return bytes([BOOL, 1 if value else 0])
    if isinstance(value, int):
        if not _INT_MIN <= value <= _INT_MAX:
            raise DataError(f"{value} is outside TinySQL's 64-bit INT")
        return bytes([INT]) + struct.pack(">q", value)
    if isinstance(value, str):
        text = value.encode("utf-8")
        return bytes([TEXT]) + struct.pack(">I", len(text)) + text
    raise TypeError(f"TinySQL has no type for {type(value).__name__}")


def encode_query(sql, params):
    text = sql.encode("utf-8")
    parts = [struct.pack(">I", len(text)), text,
             struct.pack(">H", len(params))]
    parts.extend(_encode_value(value) for value in params)
    return _message(QUERY, b"".join(parts))


def encode_terminate():
    return _message(TERMINATE, b"")


class Reader:
    """Reads one message's body from the front."""

    def __init__(self, body):
        self._body = body
        self._at = 0

    def take(self, count):
        if self._at + count > len(self._body):
            raise ValueError("message ends early")
        part = self._body[self._at:self._at + count]
        self._at += count
        return part

    def uint(self, size):
        return int.from_bytes(self.take(size), "big")

    def text(self, length_size):
        return self.take(self.uint(length_size)).decode("utf-8")

    def value(self):
        type = self.uint(1)
        if type == NULL:
            return None
        if type == INT:
            return int.from_bytes(self.take(8), "big", signed=True)
        if type == TEXT:
            return self.text(4)
        if type == BOOL:
            return self.uint(1) != 0
        raise ValueError(f"unknown value type {type}")


def decode_columns(body):
    """A list of (name, type)."""
    reader = Reader(body)
    return [(reader.text(2), reader.uint(1))
            for _ in range(reader.uint(2))]


def decode_row(body, column_count):
    reader = Reader(body)
    return tuple(reader.value() for _ in range(column_count))


def decode_complete(body):
    return Reader(body).uint(8)


def decode_error(body):
    """(sqlstate, message)."""
    reader = Reader(body)
    return reader.take(5).decode("ascii"), reader.text(4)


def decode_ready(body):
    """Whether the server has a transaction open."""
    return Reader(body).take(1) == b"T"
