# services/agent_service/tools/oracle_agent_tool/db.py
# -*- coding: utf-8 -*-
import os
import cx_Oracle

_POOL = None

def _session_init(conn, _):
    # 필요 시 스키마 지정. 실사용 계정이 기본 스키마면 생략 가능
    # cur = conn.cursor(); cur.execute("ALTER SESSION SET CURRENT_SCHEMA = LIBRA_DATA"); cur.close()
    pass

def get_pool():
    global _POOL
    if _POOL:
        return _POOL
    user = os.getenv("ORACLE_USER")
    pwd  = os.getenv("ORACLE_PASSWORD")
    dsn_raw = os.getenv("ORACLE_DSN")  # e.g., localhost:1521/XE
    ic_path = os.getenv("ORACLE_CLIENT_PATH") or ""
    if ic_path:
        try:
            cx_Oracle.init_oracle_client(lib_dir=ic_path)
        except cx_Oracle.ProgrammingError:
            pass

    # dsn 파싱
    if "/" in dsn_raw and ":" in dsn_raw:
        host_port, service = dsn_raw.split("/", 1)
        host, port = host_port.split(":", 1)
        dsn = cx_Oracle.makedsn(host.strip(), int(port), service_name=service.strip())
    else:
        dsn = dsn_raw

    _POOL = cx_Oracle.SessionPool(
        user=user, password=pwd, dsn=dsn,
        min=1, max=5, increment=1, threaded=True,
        getmode=cx_Oracle.SPOOL_ATTRVAL_NOWAIT,
        encoding="UTF-8", nencoding="UTF-8",
        sessionCallback=_session_init,
    )
    return _POOL

class ConnCtx:
    def __enter__(self):
        self.conn = get_pool().acquire()
        return self.conn
    def __exit__(self, et, ev, tb):
        try:
            if et is None: self.conn.commit()
            else: self.conn.rollback()
        finally:
            get_pool().release(self.conn)
