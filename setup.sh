#!/bin/bash
echo "Libra 프로젝트 초기 세팅 시작..."

# Python 가상환경 설정
mkdir -p .venv
python -m venv .venv/libra_env
source .venv/libra_env/bin/activate

# 라이브러리 설치
if [ -f requirements.txt ]; then
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "requirements.txt 파일 없음"
fi

# DB 폴더 및 테이블스페이스 파일 생성
mkdir -p services/user_service/db
mkdir -p services/data_service/db
mkdir -p services/web_frontend/db

touch services/user_service/db/user_db.dbf
touch services/data_service/db/data_db.dbf
touch services/web_frontend/db/web_db.dbf

echo "📦 테이블스페이스용 파일 생성 완료"

# Windows 기준 경로 변환 (Git Bash)
USER_DB_PATH=$(cygpath -w "$(pwd)/services/user_service/db/user_db.dbf")
DATA_DB_PATH=$(cygpath -w "$(pwd)/services/data_service/db/data_db.dbf")
WEB_DB_PATH=$(cygpath -w "$(pwd)/services/web_frontend/db/web_db.dbf")

# Oracle 테이블스페이스 및 계정 생성
echo "Oracle 설정 시작..."
sqlplus -s sys/Oracle123@XE as sysdba <<EOF
WHENEVER SQLERROR EXIT SQL.SQLCODE

-- 테이블스페이스 생성
CREATE TABLESPACE user_db DATAFILE '$USER_DB_PATH' SIZE 100M AUTOEXTEND ON MAXSIZE UNLIMITED;
CREATE TABLESPACE data_db DATAFILE '$DATA_DB_PATH' SIZE 100M AUTOEXTEND ON MAXSIZE UNLIMITED;
CREATE TABLESPACE web_db  DATAFILE '$WEB_DB_PATH'  SIZE 100M AUTOEXTEND ON MAXSIZE UNLIMITED;

-- 사용자 생성 및 권한 부여
CREATE USER libra_admin IDENTIFIED BY "1234";
GRANT CONNECT, RESOURCE TO libra_admin;
GRANT UNLIMITED TABLESPACE TO libra_admin;
ALTER USER libra_admin DEFAULT TABLESPACE user_db;

EXIT;
EOF

echo "Oracle 테이블스페이스 및 계정 설정 완료!"
