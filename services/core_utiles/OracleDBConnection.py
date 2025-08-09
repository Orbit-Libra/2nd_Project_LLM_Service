import os
import oracledb
from sqlalchemy import create_engine
from core_utiles.config_loader import (
    ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN, ORACLE_CLIENT_PATH
)

class OracleDBConnection:
    def __init__(self):
        self.username   = ORACLE_USER
        self.password   = ORACLE_PASSWORD
        self.dsn        = ORACLE_DSN
        self.client_dir = ORACLE_CLIENT_PATH

        self.conn       = None          # oracledb connection
        self.cursor     = None
        self.engine     = None          # SQLAlchemy engine 객체

        self._init_client()

    def _init_client(self):
        try:
            oracledb.init_oracle_client(lib_dir=self.client_dir)
        except Exception as e:
            print("[오류] Oracle Instant Client 초기화 실패:", e)

    def connect(self):
        try:
            self.conn = oracledb.connect(
                user=self.username,
                password=self.password,
                dsn=self.dsn
            )
            self.cursor = self.conn.cursor()

            # SQLAlchemy 엔진 생성
            dsn_str = f'oracle+oracledb://{self.username}:{self.password}@{self.dsn}'
            self.engine = create_engine(dsn_str)

            print("Oracle DB 접속 성공")
        except Exception as e:
            print("[오류] Oracle DB 연결 실패:", e)

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("DB 연결 종료")

    def execute_query(self, query):
        if not self.cursor:
            raise Exception("DB 연결이 없습니다. 먼저 connect()를 호출하세요.")
        self.cursor.execute(query)
        return self.cursor.fetchall()