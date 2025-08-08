import os
import cx_Oracle
from flask import Blueprint, request, jsonify
from dotenv import load_dotenv

# === .env 로드 (data_service/.env 우선) ===
THIS_DIR = os.path.dirname(__file__)
DATA_SERVICE_DIR = os.path.abspath(os.path.join(THIS_DIR, ".."))
ENV_PATH = os.path.join(DATA_SERVICE_DIR, ".env")
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
else:
    # 루트에도 있을 수 있으니 한 번 더 시도
    ROOT = os.path.abspath(os.path.join(THIS_DIR, "../../../"))
    load_dotenv(os.path.join(ROOT, ".env"))

ORACLE_USER = os.getenv("ORACLE_USER", "")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "")
ORACLE_DSN = os.getenv("ORACLE_DSN", "")
ORACLE_CLIENT_PATH = os.getenv("ORACLE_CLIENT_PATH", "")
ORACLE_SCHEMA = os.getenv("ORACLE_SCHEMA", ORACLE_USER)  # 보통 사용자명

try:
    if ORACLE_CLIENT_PATH and os.path.isdir(ORACLE_CLIENT_PATH):
        cx_Oracle.init_oracle_client(lib_dir=ORACLE_CLIENT_PATH)
except Exception as e:
    print(f"[num06_api] oracle_client init warn: {e}")

_pool = None

def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    if not (ORACLE_USER and ORACLE_PASSWORD and ORACLE_DSN):
        raise RuntimeError("Oracle env missing (ORACLE_USER/ORACLE_PASSWORD/ORACLE_DSN).")
    _pool = cx_Oracle.SessionPool(
        user=ORACLE_USER,
        password=ORACLE_PASSWORD,
        dsn=ORACLE_DSN,
        min=1, max=4, increment=1,
        encoding="UTF-8",
        threaded=True
    )
    print("[num06_api] Oracle SessionPool created:", ORACLE_DSN)
    return _pool

def _acquire():
    return _get_pool().acquire()

def _q_ident(name: str) -> str:
    if not name:
        raise ValueError("empty identifier")
    if name[0].isdigit():
        return f'"{name}"'
    if all(c.isalnum() or c == '_' for c in name):
        return name
    return f'"{name}"'

def _table_name_num06(year: int) -> str:
    # 요청 year를 그대로 사용 — 전역 상태/캐시 사용 절대 금지
    base = f'NUM06_{int(year)}'
    tbl = _q_ident(base)
    if ORACLE_SCHEMA:
        return f'{_q_ident(ORACLE_SCHEMA)}.{tbl}'
    return tbl

num06_bp = Blueprint("num06_bp", __name__, url_prefix="/api")

@num06_bp.get("/num06-metrics")
def num06_metrics():
    # 1) 파라미터 강제 변환
    year_str = request.args.get("year", "").strip()
    snm = request.args.get("snm", "").strip()
    if not snm or not year_str:
        return jsonify(success=False, error="snm, year 는 필수입니다."), 400

    try:
        year = int(year_str)
    except ValueError:
        return jsonify(success=False, error=f"year 파라미터가 정수가 아닙니다: {year_str}"), 400

    table = _table_name_num06(year)

    col_cps = _q_ident("CPSS_CPS")
    col_lps = _q_ident("LPS_LPS")
    col_vps = _q_ident("VPS_VPS")

    sql = f"""
        SELECT {col_cps}, {col_lps}, {col_vps}
        FROM {table}
        WHERE SNM = :snm
    """.strip()

    # 디버그 로그: 요청된 year와 실제 테이블명 같이 찍기
    print(f"[num06_api] REQ year={year}, table={table}")
    print(f"[num06_api] SQL => {sql} | binds = snm:{snm}")

    conn = cur = None
    try:
        conn = _acquire()
        cur = conn.cursor()
        cur.execute(sql, {"snm": snm})
        row = cur.fetchone()
        if not row:
            return jsonify(success=False, error="해당 대학/연도 데이터가 없습니다.", table=table), 404

        cps, lps, vps = row
        return jsonify(success=True, data={"CPS": cps, "LPS": lps, "VPS": vps, "table": table})
    except cx_Oracle.DatabaseError as e:
        # 오라클 에러 원문 그대로 반환 (디버깅 편의)
        return jsonify(success=False, error=str(e), table=table), 500
    except Exception as e:
        return jsonify(success=False, error=str(e), table=table), 500
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except Exception:
            pass

@num06_bp.get("/health")
def health():
    try:
        conn = _acquire()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM DUAL")
        cur.fetchone()
        cur.close()
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass
