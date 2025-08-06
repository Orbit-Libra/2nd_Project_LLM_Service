@echo off
SETLOCAL ENABLEDELAYEDEXPANSION
chcp 65001 >nul

echo [🔧] Libra 프로젝트 초기 세팅 시작...

REM ==============================
REM 1. Python 가상환경 설정
REM ==============================
IF EXIST .venv\libra_env\Scripts\activate.bat (
    echo [⏭️] 가상환경 이미 존재. 생략합니다.
    call .venv\libra_env\Scripts\activate.bat
) ELSE (
    echo [🐍] 가상환경 생성 중...
    IF NOT EXIST .venv mkdir .venv
    python -m venv .venv\libra_env
    call .venv\libra_env\Scripts\activate.bat

    IF EXIST requirements.txt (
        echo [📦] 라이브러리 설치 중...
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    ) ELSE (
        echo [⚠] requirements.txt 파일이 없습니다.
    )
)

REM ==============================
REM 2. DB 폴더 생성
REM ==============================
IF NOT EXIST services\user_service\db mkdir services\user_service\db >nul 2>nul
IF NOT EXIST services\data_service\db mkdir services\data_service\db >nul 2>nul
IF NOT EXIST services\web_frontend\db mkdir services\web_frontend\db >nul 2>nul
echo [📁] 테이블스페이스 폴더 생성 완료

REM ==============================
REM 3. 경로 추출
REM ==============================
SET "USER_DB_PATH=%CD%\services\user_service\db\user_db.dbf"
SET "DATA_DB_PATH=%CD%\services\data_service\db\data_db.dbf"
SET "WEB_DB_PATH=%CD%\services\web_frontend\db\web_db.dbf"
echo [📌] .dbf 경로 자동 계산 완료

REM ==============================
REM 4. 테이블스페이스 존재 확인
REM ==============================
echo [🔍] 테이블스페이스 존재 확인 중...
SET CHECK_TS_SQL=check_tablespace.sql
(
echo SET HEADING OFF
echo SET FEEDBACK OFF
echo SET PAGESIZE 0
echo SELECT COUNT^(*^) FROM dba_tablespaces WHERE tablespace_name IN ^('USER_DB', 'DATA_DB', 'WEB_DB'^);
echo EXIT;
) > %CHECK_TS_SQL%

SET FOUND_TS=0
FOR /F "tokens=*" %%A IN ('sqlplus -s sys/Oracle123@XE as sysdba @%CHECK_TS_SQL% 2^>nul') DO (
    IF "%%A"=="3" SET FOUND_TS=1
)
del %CHECK_TS_SQL% >nul 2>nul

REM ==============================
REM 5. 사용자 계정 존재 확인
REM ==============================
echo [🔍] 사용자 계정 존재 확인 중...
SET CHECK_USER_SQL=check_users.sql
(
echo SET HEADING OFF
echo SET FEEDBACK OFF
echo SET PAGESIZE 0
echo SELECT COUNT^(*^) FROM dba_users WHERE username IN ^('LIBRA_USER', 'LIBRA_DATA', 'LIBRA_WEB'^);
echo EXIT;
) > %CHECK_USER_SQL%

SET FOUND_USERS=0
FOR /F "tokens=*" %%B IN ('sqlplus -s sys/Oracle123@XE as sysdba @%CHECK_USER_SQL% 2^>nul') DO (
    IF "%%B"=="3" SET FOUND_USERS=1
)
del %CHECK_USER_SQL% >nul 2>nul

REM ==============================
REM 6. Oracle 설정 실행
REM ==============================
IF %FOUND_TS%==1 (
    echo [⏭️] 테이블스페이스 이미 존재. 생략합니다.
) ELSE (
    echo [📦] 테이블스페이스 생성 중...
    SET CREATE_TS=1
)

IF %FOUND_USERS%==1 (
    echo [⏭️] 사용자 계정 이미 존재. 생략합니다.
) ELSE (
    echo [👤] 사용자 계정 생성 중...
    SET CREATE_USERS=1
)

REM 생성이 필요한 경우에만 SQL 실행
IF DEFINED CREATE_TS (SET NEED_SQL=1)
IF DEFINED CREATE_USERS (SET NEED_SQL=1)

IF DEFINED NEED_SQL (
    echo [🧠] Oracle 설정 중...
    SET TEMP_SQL_FILE=oracle_setup_temp.sql
    (
    echo -- 오류 발생 시에도 계속 진행
    echo WHENEVER SQLERROR CONTINUE
    echo.
    IF DEFINED CREATE_TS (
        echo -- 테이블스페이스 생성 ^(이미 존재하면 무시^)
        echo BEGIN
        echo     EXECUTE IMMEDIATE 'CREATE TABLESPACE user_db DATAFILE ''!USER_DB_PATH!'' SIZE 100M AUTOEXTEND ON MAXSIZE UNLIMITED';
        echo     DBMS_OUTPUT.PUT_LINE^('USER_DB 생성 완료'^);
        echo EXCEPTION
        echo     WHEN OTHERS THEN
        echo         IF SQLCODE != -1543 THEN RAISE; END IF;
        echo END;
        echo /
        echo.
        echo BEGIN
        echo     EXECUTE IMMEDIATE 'CREATE TABLESPACE data_db DATAFILE ''!DATA_DB_PATH!'' SIZE 100M AUTOEXTEND ON MAXSIZE UNLIMITED';
        echo     DBMS_OUTPUT.PUT_LINE^('DATA_DB 생성 완료'^);
        echo EXCEPTION
        echo     WHEN OTHERS THEN
        echo         IF SQLCODE != -1543 THEN RAISE; END IF;
        echo END;
        echo /
        echo.
        echo BEGIN
        echo     EXECUTE IMMEDIATE 'CREATE TABLESPACE web_db DATAFILE ''!WEB_DB_PATH!'' SIZE 100M AUTOEXTEND ON MAXSIZE UNLIMITED';
        echo     DBMS_OUTPUT.PUT_LINE^('WEB_DB 생성 완료'^);
        echo EXCEPTION
        echo     WHEN OTHERS THEN
        echo         IF SQLCODE != -1543 THEN RAISE; END IF;
        echo END;
        echo /
        echo.
    )
    IF DEFINED CREATE_USERS (
        echo -- 사용자 계정 생성 ^(이미 존재하면 무시^)
        echo BEGIN
        echo     EXECUTE IMMEDIATE 'CREATE USER libra_user IDENTIFIED BY 1234 DEFAULT TABLESPACE user_db';
        echo     EXECUTE IMMEDIATE 'ALTER USER libra_user QUOTA UNLIMITED ON user_db';
        echo     EXECUTE IMMEDIATE 'ALTER USER libra_user QUOTA 0M ON data_db';
        echo     EXECUTE IMMEDIATE 'ALTER USER libra_user QUOTA 0M ON web_db';
        echo     EXECUTE IMMEDIATE 'GRANT CONNECT, RESOURCE TO libra_user';
        echo     DBMS_OUTPUT.PUT_LINE^('LIBRA_USER 생성 완료'^);
        echo EXCEPTION
        echo     WHEN OTHERS THEN
        echo         IF SQLCODE != -1920 THEN RAISE; END IF;
        echo END;
        echo /
        echo.
        echo BEGIN
        echo     EXECUTE IMMEDIATE 'CREATE USER libra_data IDENTIFIED BY 1234 DEFAULT TABLESPACE data_db';
        echo     EXECUTE IMMEDIATE 'ALTER USER libra_data QUOTA UNLIMITED ON data_db';
        echo     EXECUTE IMMEDIATE 'ALTER USER libra_data QUOTA 0M ON user_db';
        echo     EXECUTE IMMEDIATE 'ALTER USER libra_data QUOTA 0M ON web_db';
        echo     EXECUTE IMMEDIATE 'GRANT CONNECT, RESOURCE TO libra_data';
        echo     DBMS_OUTPUT.PUT_LINE^('LIBRA_DATA 생성 완료'^);
        echo EXCEPTION
        echo     WHEN OTHERS THEN
        echo         IF SQLCODE != -1920 THEN RAISE; END IF;
        echo END;
        echo /
        echo.
        echo BEGIN
        echo     EXECUTE IMMEDIATE 'CREATE USER libra_web IDENTIFIED BY 1234 DEFAULT TABLESPACE web_db';
        echo     EXECUTE IMMEDIATE 'ALTER USER libra_web QUOTA UNLIMITED ON web_db';
        echo     EXECUTE IMMEDIATE 'ALTER USER libra_web QUOTA 0M ON user_db';
        echo     EXECUTE IMMEDIATE 'ALTER USER libra_web QUOTA 0M ON data_db';
        echo     EXECUTE IMMEDIATE 'GRANT CONNECT, RESOURCE TO libra_web';
        echo     DBMS_OUTPUT.PUT_LINE^('LIBRA_WEB 생성 완료'^);
        echo EXCEPTION
        echo     WHEN OTHERS THEN
        echo         IF SQLCODE != -1920 THEN RAISE; END IF;
        echo END;
        echo /
    )
    echo.
    echo EXIT;
    ) > "!TEMP_SQL_FILE!"

    sqlplus -s sys/Oracle123@XE as sysdba @"!TEMP_SQL_FILE!" >nul 2>nul
    del "!TEMP_SQL_FILE!" >nul 2>nul
)

echo [✅] Libra Setup End.
pause
ENDLOCAL