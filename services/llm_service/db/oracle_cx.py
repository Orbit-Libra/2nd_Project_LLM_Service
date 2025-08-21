# services/llm_service/db/oracle_cx.py
import os
import cx_Oracle

_pool = None

def init_client_if_needed():
    lib_dir = (os.getenv("ORACLE_CLIENT_PATH") or "").strip()
    if lib_dir:
        try:
            cx_Oracle.init_oracle_client(lib_dir=lib_dir)
        except cx_Oracle.ProgrammingError:
            pass

def make_dsn():
    dsn_raw = (os.getenv("ORACLE_DSN") or "").strip()
    if not dsn_raw:
        raise RuntimeError("ORACLE_DSN is not set, e.g. localhost:1521/XE")
    if "/" in dsn_raw and ":" in dsn_raw:
        host_port, service = dsn_raw.split("/", 1)
        host, port = host_port.split(":", 1)
        return cx_Oracle.makedsn(host.strip(), int(port), service_name=service.strip())
    return dsn_raw

def _session_init(conn, _):
    cur = conn.cursor()
    cur.execute("ALTER SESSION SET CURRENT_SCHEMA = LIBRA_USER")
    cur.close()

def get_pool():
    global _pool
    if _pool:
        return _pool

    init_client_if_needed()
    user = os.getenv("ORACLE_USER")
    pwd  = os.getenv("ORACLE_PASSWORD")
    dsn  = make_dsn()

    _pool = cx_Oracle.SessionPool(
        user=user,
        password=pwd,
        dsn=dsn,
        min=1, max=5, increment=1,
        threaded=True,
        getmode=cx_Oracle.SPOOL_ATTRVAL_NOWAIT,
        encoding="UTF-8", nencoding="UTF-8",
        sessionCallback=_session_init,
    )
    return _pool

class ConnCtx:
    def __init__(self):
        self.conn = None
    def __enter__(self):
        self.conn = get_pool().acquire()
        return self.conn
    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None: self.conn.commit()
            else: self.conn.rollback()
        finally:
            get_pool().release(self.conn)

def acquire():
    return get_pool().acquire()
