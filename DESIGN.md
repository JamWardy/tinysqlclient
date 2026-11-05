# How tinysqlclient works

A Python client for TinySQL's server, as psycopg is for Postgres. It's
a project of its own: the shop's services import it, and it imports
nothing beyond Python's own `socket` and `struct`.

## The protocol

The client speaks the server's protocol as `../tinysql/src/server/protocol.h`
describes it. That file is the one place the messages are defined; this
one says only how the client uses them.

A query is one `'Q'` sent, then messages read until `'Z'`: `T` gives
the columns, each `D` a row, `C` the count of rows changed, and `E` an
error. The client always reads to `Z`, even after an `E`, so the next
query starts on its own reply. TCP may split a message anywhere, so
each read loops until it has the bytes it asked for.

All of a query's rows are read before `execute` returns, as psycopg's
default cursor does.

## Values

| TinySQL | Python |
|---|---|
| `NULL` | `None` |
| `INT` | `int` |
| `TEXT` | `str`, sent as UTF-8; the length is in bytes |
| `BOOL` | `bool` |

`bool` is checked before `int`, as `True` is also an `int`. An `int`
outside 64 bits, or any other type such as `float`, raises `DataError`
or `TypeError` before anything is sent.

## Interface

The parts of PEP 249 (DB-API 2.0) the services use, as sqlite3 and
psycopg follow it:

- `connect(host="127.0.0.1", port=5480)` returns a `Connection`.
- `Connection`: `cursor()`, `transaction()` and `close()`, which sends
  `'X'`.
- `Cursor`: `execute(sql, params=())`, `fetchone()`, `fetchall()`,
  `description` (one 7-item tuple per column, name and type filled in)
  and `rowcount`: the rows given back, or for a statement that gives
  none, the rows changed (from `C`), as psycopg's is.
- Statements end in `;`, as TinySQL's grammar asks; the client sends
  the SQL as it's given.
- `paramstyle = "qmark"`, as TinySQL's parameters are `?`.

### Transactions

The connection is in autocommit mode: each statement outside a
transaction commits on its own, and nothing is begun for you. PEP 249's
default, beginning a transaction before the first statement, would let
a service that forgot to commit after a plain `SELECT` hold up every
other client until the idle timeout, as TinySQL runs one transaction at
a time.

A transaction is `with conn.transaction():`, as in psycopg 3. It sends
`BEGIN`, then `COMMIT` if the block finishes, or `ROLLBACK` if it
raises. The `'Z'` after each query says whether the server still has a
transaction open, and `ROLLBACK` is sent only if it has, since one
rolled back for being idle too long is already gone.

## Errors

PEP 249's exceptions, chosen by the SQLSTATE's first two characters, as
psycopg does. Each has the code as `sqlstate` and the server's message.

| Class | Exception | Such as |
|---|---|---|
| `22` | `DataError` | `22003` out of range, `22012` division by zero |
| `23` | `IntegrityError` | `23505` a broken `UNIQUE`, `23502` a `NULL` in a `NOT NULL` |
| `42` | `ProgrammingError` | `42601` syntax, `42P01` no such table |
| `0A` | `NotSupportedError` | |
| `08`, `25`, `53`, `54`, `55`, `58` | `OperationalError` | `25P03` rolled back after idling, `25006` a change sent to the replica |
| `XX` | `InternalError` | a bug in TinySQL, or a corrupted file |

The order service catches `IntegrityError` with `sqlstate == "23505"`
to spot a repeated idempotency key.

## Connections

Each service process opens one connection when it starts and keeps it.
tinyhttp answers one request at a time, so there's nothing for a pool
to share yet; one comes with pre-fork workers or threads.

A dropped socket, or a reply the client can't read, raises
`OperationalError` and closes the connection.
The next `execute` opens a new one. The statement that failed is never
sent again: the server may have run it before the socket dropped, and
an `INSERT` run twice is a second row.

There's no timeout, as psycopg has none by default. A query may wait
behind another client's transaction, and the server's idle timeout
bounds that.
