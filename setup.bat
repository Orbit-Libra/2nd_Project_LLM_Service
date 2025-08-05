@echo off
SETLOCAL ENABLEDELAYEDEXPANSION
chcp 65001 >nul

echo [🔧] Libra 프로젝트 초기 세팅 시작...

REM ──────────────────────────────
REM 1. Python 가상환경 설정
REM ──────────────────────────────
mkdir .venv
python -m venv .venv\libra_env
call .venv\libra_env\Scripts\activate.bat

IF EXIST requirements.txt (
    echo [🐍] 라이브러리 설치 중...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) ELSE (
    echo [⚠] requirements.txt 파일이 없습니다.
)

REM ──────────────────────────────
REM 2. DB 폴더 생성
REM ──────────────────────────────
mkdir services\user_service\db >nul 2>nul
mkdir services\data_service\db >nul 2>nul
mkdir services\web_frontend\db >nul 2>nul
echo [📁] 테이블스페이스 폴더 생성 완료

REM ──────────────────────────────
REM 3. 경로 추출
REM ──────────────────────────────
SET "USER_DB_PATH=%CD%\services\user_service\db\user_db.dbf"
SET "DATA_DB_PATH=%CD%\services\data_service\db\data_db.dbf"
SET "WEB_DB_PATH=%CD%\services\web_frontend\db\web_db.dbf"
echo [📌] .dbf 경로 자동 계산 완료

REM ──────────────────────────────
REM 4. SQL 파일 생성
REM ──────────────────────────────
SET TEMP_SQL_FILE=__oracle_setup_temp.sql
(
echo WHENEVER SQLERROR EXIT SQL.SQLCODE
echo.
echo CREATE TABLESPACE user_db DATAFILE '!USER_DB_PATH!' SIZE 100M AUTOEXTEND ON MAXSIZE UNLIMITED;
echo CREATE TABLESPACE data_db DATAFILE '!DATA_DB_PATH!' SIZE 100M AUTOEXTEND ON MAXSIZE UNLIMITED;
echo CREATE TABLESPACE web_db  DATAFILE '!WEB_DB_PATH!'  SIZE 100M AUTOEXTEND ON MAXSIZE UNLIMITED;
echo.
echo CREATE USER libra_user IDENTIFIED BY 1234 DEFAULT TABLESPACE user_db;
echo ALTER USER libra_user QUOTA UNLIMITED ON user_db;
echo ALTER USER libra_user QUOTA 0M ON data_db;
echo ALTER USER libra_user QUOTA 0M ON web_db;
echo GRANT CONNECT, RESOURCE TO libra_user;
echo.
echo CREATE USER libra_data IDENTIFIED BY 1234 DEFAULT TABLESPACE data_db;
echo ALTER USER libra_data QUOTA UNLIMITED ON data_db;
echo ALTER USER libra_data QUOTA 0M ON user_db;
echo ALTER USER libra_data QUOTA 0M ON web_db;
echo GRANT CONNECT, RESOURCE TO libra_data;
echo.
echo CREATE USER libra_web IDENTIFIED BY 1234 DEFAULT TABLESPACE web_db;
echo ALTER USER libra_web QUOTA UNLIMITED ON web_db;
echo ALTER USER libra_web QUOTA 0M ON user_db;
echo ALTER USER libra_web QUOTA 0M ON data_db;
echo GRANT CONNECT, RESOURCE TO libra_web;
echo.
echo EXIT;
) > %TEMP_SQL_FILE%

REM ──────────────────────────────
REM 5. Oracle SQL 실행
REM ──────────────────────────────
echo [🧠] Oracle 설정 중...
sqlplus -s sys/Oracle123@XE as sysdba @%TEMP_SQL_FILE%

REM ──────────────────────────────
REM 6. 정리
REM ──────────────────────────────
del %TEMP_SQL_FILE%
echo [✅] 모든 계정 설정 및 초기화 완료!

ENDLOCAL
