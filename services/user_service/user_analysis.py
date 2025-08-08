# services/user_service/user_analysis.py
import os, requests
import cx_Oracle
from flask import Blueprint, jsonify, session
from services.web_frontend.api.oracle_utils import get_connection

bp_user_analysis = Blueprint('bp_user_analysis', __name__, url_prefix='/api/user')

DATA_SERVICE_BASE = os.getenv('DATA_SERVICE_URL', 'http://localhost:5050')


def _q(col: str) -> str:
    """숫자로 시작하거나 identifier가 아니면 쿼트."""
    if not col:
        return col
    return f'"{col}"' if (col[0].isdigit() or not col.isidentifier()) else col


def _to_float_or_none(v):
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        try:
            s = str(v).strip()
            return float(s) if s else None
        except Exception:
            return None


# TODO: 5050 데이터서비스 붙이면 실제 값으로 교체
def fetch_univ_metrics(snm: str, year: int):
    url = f"{DATA_SERVICE_BASE}/api/num06-metrics"
    try:
        r = requests.get(url, params={"snm": snm, "year": year}, timeout=5)
    except requests.RequestException as e:
        print('[analysis][WARN] 5050 연결 실패:', e)
        return {'CPS': 0, 'LPS': 0, 'VPS': 0, '_err': 'connect-failed'}

    if not r.ok:
        print('[analysis][WARN] 5050 응답 에러:', r.status_code, r.text[:200])
        return {'CPS': 0, 'LPS': 0, 'VPS': 0, '_err': 'bad-status'}

    body = r.json()
    if not body.get('success'):
        print('[analysis][WARN] 5050 실패:', body)
        return {'CPS': 0, 'LPS': 0, 'VPS': 0, '_err': 'api-failed'}

    data = body.get('data', {})
    # 방어적 캐스팅
    def f(x): 
        try: return float(x)
        except: return 0.0
    return {'CPS': f(data.get('CPS')), 'LPS': f(data.get('LPS')), 'VPS': f(data.get('VPS'))}


def fetch_all_univ_scores(year: int, conn):
    """유사대학 비교용: 특정 연도의 모든 대학 점수(SNM, score)"""
    score_col = f"SCR_EST_{year}"
    q_score = _q(score_col)
    sql = f"SELECT SNM, {q_score} FROM ESTIMATIONFUTURE WHERE {q_score} IS NOT NULL"
    print('[analysis] all_univ_scores SQL =>', sql)
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        print('[analysis] all_univ_scores rows =>', len(rows))
        out = []
        for snm, score in rows:
            s = _to_float_or_none(score)
            if s is not None:
                out.append({'SNM': snm, 'score': s})
        return out
    finally:
        if cur:
            cur.close()


@bp_user_analysis.get('/analysis')
def analysis():
    usr_id = session.get('user')
    if not usr_id:
        return jsonify(success=False, error='로그인이 필요합니다.'), 401

    print('[analysis] user =>', usr_id)

    conn = None
    cur = None
    try:
        conn = get_connection()
        print('[analysis] DB 연결 OK')

        # USER_DATA에서 읽을 컬럼
        cols = [
            'USR_NAME', 'USR_SNM',
            '1ST_YR', '1ST_USR_CPS', '1ST_USR_LPS', '1ST_USR_VPS', 'SCR_EST_1ST',
            '2ND_YR', '2ND_USR_CPS', '2ND_USR_LPS', '2ND_USR_VPS', 'SCR_EST_2ND',
            '3RD_YR', '3RD_USR_CPS', '3RD_USR_LPS', '3RD_USR_VPS', 'SCR_EST_3RD',
            '4TH_YR', '4TH_USR_CPS', '4TH_USR_LPS', '4TH_USR_VPS', 'SCR_EST_4TH',
        ]
        select_cols = ','.join(_q(c) for c in cols)
        sql_user = f"SELECT {select_cols} FROM USER_DATA WHERE USR_ID = :1"
        print('[analysis] USER_DATA SQL =>', sql_user, '| binds =', [usr_id])

        # ✅ cursor 생성 후 실행 (named bind 일관)
        cur = conn.cursor()
        cur.execute(sql_user, [usr_id])
        row = cur.fetchone()
        cur.close()
        cur = None

        if not row:
            print('[analysis] USER_DATA row => None')
            return jsonify(success=False, error='유저 데이터를 찾을 수 없습니다.'), 404

        print('[analysis] USER_DATA row len =>', len(row))

        # 파싱
        idx = 0
        usr_name = row[idx]; idx += 1
        usr_snm  = row[idx]; idx += 1

        def take_grade():
            nonlocal idx
            y   = row[idx]; idx += 1
            cps = row[idx]; idx += 1
            lps = row[idx]; idx += 1
            vps = row[idx]; idx += 1
            scr = row[idx]; idx += 1
            return y, cps, lps, vps, scr

        y1, cps1, lps1, vps1, scr1 = take_grade()
        y2, cps2, lps2, vps2, scr2 = take_grade()
        y3, cps3, lps3, vps3, scr3 = take_grade()
        y4, cps4, lps4, vps4, scr4 = take_grade()

        print('[analysis] basics =>', {'usr_name': usr_name, 'usr_snm': usr_snm, 'y1': y1, 'y2': y2, 'y3': y3, 'y4': y4})

        def build_grade(year, cps, lps, vps, user_scr):
            if not year:
                return None
            try:
                year = int(year)
            except Exception:
                print('[analysis] skip invalid year =>', year)
                return None

            print(f'[analysis] build grade {year}')

            # 대학 3종(5050 자리)
            try:
                univ_metrics = fetch_univ_metrics(usr_snm, year)
            except Exception as e:
                print('[analysis][WARN] fetch_univ_metrics 실패:', e)
                univ_metrics = {'CPS': 0, 'LPS': 0, 'VPS': 0}

            # 유사대학 풀
            try:
                by_scores = fetch_all_univ_scores(year, conn)
            except Exception as e:
                print('[analysis][WARN] fetch_all_univ_scores 실패:', e)
                by_scores = []

            # 소속대학 점수
            univ_scr = None
            c2 = None
            try:
                q_col = _q(f"SCR_EST_{year}")
                sql_univ = f"SELECT {q_col} FROM ESTIMATIONFUTURE WHERE SNM = :snm"
                print('[analysis] univ score SQL =>', sql_univ, '| snm =', usr_snm)
                c2 = conn.cursor()
                c2.execute(sql_univ, {'snm': usr_snm})
                r = c2.fetchone()
                univ_scr = _to_float_or_none(r[0]) if r else None
            except Exception as e:
                print('[analysis][WARN] 소속대학 점수 조회 실패:', e)
            finally:
                if c2:
                    c2.close()

            return {
                'year': year,
                'userData': {
                    'CPS': _to_float_or_none(cps) or 0,
                    'LPS': _to_float_or_none(lps) or 0,
                    'VPS': _to_float_or_none(vps) or 0
                },
                'universityData': {
                    'CPS': _to_float_or_none(univ_metrics.get('CPS')) or 0,
                    'LPS': _to_float_or_none(univ_metrics.get('LPS')) or 0,
                    'VPS': _to_float_or_none(univ_metrics.get('VPS')) or 0
                },
                'userScore': _to_float_or_none(user_scr),
                'universityScore': univ_scr,
                'byYearScores': by_scores
            }

        grades = {
            1: build_grade(y1, cps1, lps1, vps1, scr1),
            2: build_grade(y2, cps2, lps2, vps2, scr2),
            3: build_grade(y3, cps3, lps3, vps3, scr3),
            4: build_grade(y4, cps4, lps4, vps4, scr4),
        }
        grades = {k: v for k, v in grades.items() if v}

        print('[analysis] grades keys =>', list(grades.keys()))
        return jsonify(success=True, user={'name': usr_name, 'snm': usr_snm}, grades=grades)

    except cx_Oracle.DatabaseError as e:
        print('[analysis][ERR] DB 오류:', e)
        return jsonify(success=False, error=f'DB 조회 오류: {e}'), 500
    except Exception as e:
        print('[analysis][ERR]', e)
        return jsonify(success=False, error=str(e)), 500
    finally:
        try:
            if cur:
                cur.close()
        finally:
            if conn:
                conn.close()
