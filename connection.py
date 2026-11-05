import contextlib
import socket

from . import protocol
from .errors import Error, InterfaceError, OperationalError, \
    ProgrammingError, error_for


class Connection:
    def __init__(self, host, port):
        self._address = (host, port)
        self._sock = None
        self._closed = False
        # What the server's last 'Z' said.
        self._in_transaction = False
        # Inside transaction(), so a dropped socket mustn't be replaced: the
        # rest of the block would run outside the transaction.
        self._in_block = False
        self._open()

    def cursor(self):
        return Cursor(self)

    @contextlib.contextmanager
    def transaction(self):
        if self._in_block:
            raise ProgrammingError("already in a transaction")
        self._run("BEGIN;", ())
        self._in_block = True
        try:
            yield
            self._run("COMMIT;", ())
        except BaseException:
            # Not if the server already rolled it back, for idling.
            if self._in_transaction:
                self._run("ROLLBACK;", ())
            raise
        finally:
            self._in_block = False

    def close(self):
        if self._sock is not None:
            try:
                self._sock.sendall(protocol.encode_terminate())
            except OSError:
                pass
            self._drop()
        self._closed = True

    def _open(self):
        try:
            self._sock = socket.create_connection(self._address)
        except OSError as e:
            raise OperationalError(
                f"can't connect to TinySQL at {self._address}: {e}") from e

    def _drop(self):
        self._sock.close()
        self._sock = None
        self._in_transaction = False

    def _run(self, sql, params):
        """Sends one statement; returns (columns, rows, changed)."""
        if self._closed:
            raise InterfaceError("connection is closed")
        if self._sock is None:
            if self._in_block:
                raise OperationalError("connection lost in a transaction")
            self._open()
        # Encoded first, so a bad value leaves the connection as it was.
        message = protocol.encode_query(sql, params)

        columns, rows, changed, error = None, [], 0, None
        try:
            self._sock.sendall(message)
            while True:
                type, body = self._read_message(error)
                if type == protocol.COLUMNS:
                    columns = protocol.decode_columns(body)
                elif type == protocol.ROW:
                    rows.append(protocol.decode_row(body, len(columns)))
                elif type == protocol.COMPLETE:
                    changed = protocol.decode_complete(body)
                elif type == protocol.ERROR:
                    error = protocol.decode_error(body)
                elif type == protocol.READY:
                    self._in_transaction = protocol.decode_ready(body)
                    break
                else:
                    raise ValueError(f"unexpected message {type!r}")
        except OSError as e:
            self._drop()
            raise OperationalError(f"connection to TinySQL lost: {e}") from e
        except (ValueError, TypeError) as e:
            self._drop()
            raise OperationalError(f"bad reply from TinySQL: {e}") from e
        except Error:
            # The server's error before it closed the connection.
            self._drop()
            raise

        if error is not None:
            raise error_for(*error)
        return columns, rows, changed

    def _read_message(self, error):
        type, length = protocol.HEADER.unpack(self._recv_exact(5, error))
        return type, self._recv_exact(length, error)

    def _recv_exact(self, count, error):
        chunks = []
        while count > 0:
            chunk = self._sock.recv(min(count, 65536))
            if not chunk:
                # The server sends an error before closing a connection it
                # refuses, so that's the better message.
                if error is not None:
                    raise error_for(*error)
                raise OperationalError("TinySQL closed the connection")
            chunks.append(chunk)
            count -= len(chunk)
        return b"".join(chunks)


class Cursor:
    arraysize = 1

    def __init__(self, connection):
        self._connection = connection
        self.close()

    def execute(self, sql, params=()):
        # So a failed statement doesn't leave the last one's rows to fetch.
        self.close()
        columns, rows, changed = self._connection._run(sql, params)
        if columns is None:
            self.description = None
            self.rowcount = changed
        else:
            self.description = tuple(
                (name, type, None, None, None, None, None)
                for name, type in columns)
            self.rowcount = len(rows)
        self._rows = rows
        self._next = 0

    def fetchone(self):
        self._check_rows()
        if self._next == len(self._rows):
            return None
        self._next += 1
        return self._rows[self._next - 1]

    def fetchall(self):
        self._check_rows()
        rows = self._rows[self._next:]
        self._next = len(self._rows)
        return rows

    def close(self):
        self.description = None
        self.rowcount = -1
        self._rows = []
        self._next = 0

    def _check_rows(self):
        if self.description is None:
            raise ProgrammingError("the last statement gave no rows")
