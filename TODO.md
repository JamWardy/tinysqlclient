# TODO

How it works is in `DESIGN.md`.

```
tinysqlclient/
  __init__.py     connect(), paramstyle, and the rest re-exported
  errors.py       the exceptions
  protocol.py     values and messages to and from bytes, no socket
  connection.py   Connection and Cursor
```

- [x] `protocol.py`: encoding a `'Q'` and its values, and decoding
      `T`, `D`, `C`, `E` and `Z`, as `DESIGN.md` describes under "The
      protocol" and "Values"
- [x] `connection.py`: `connect`, `execute` reading to `Z`, `fetchone`,
      `fetchall`, `description`, `rowcount` and `close`, as under
      "Interface"
- [x] The exceptions, by SQLSTATE class, as under "Errors"
- [x] `transaction()`, as under "Transactions"
- [x] Reconnecting after a dropped socket, as under "Connections"
- [x] Try it by hand against `tinysql-server` on a scratch database: a
      `SELECT`, an `INSERT ... RETURNING`, a broken `UNIQUE`, a
      transaction left past the idle timeout, and the server restarted
      between queries
