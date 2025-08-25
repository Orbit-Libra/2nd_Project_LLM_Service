# services/user_service/init_oracle_qna.py
import os
import cx_Oracle
from dotenv import load_dotenv

"""
Q&A 스키마 1회성 초기화 스크립트
- QNA_POSTS, QNA_COMMENTS 테이블
- 시퀀스(QNA_POSTS_SEQ, QNA_COMMENTS_SEQ, 첨부전용 QNA_FILES_SEQ)
- 인덱스/제약(FK, ON DELETE CASCADE)
- 여러 번 실행되어도 안전하도록 EXCEPTION NULL 처리
"""

# 1) .env 로드 (services/user_service/.env 우선)
here = os.path.dirname(os.path.abspath(__file__))
candidate_env_paths = [
    os.path.join(here, '.env'),
    os.path.abspath(os.path.join(here, '..', 'services', 'user_service', '.env')),
    os.path.abspath(os.path.join(here, '..', 'user_service', '.env')),
    os.path.abspath(os.path.join(here, '..', '..', 'services', 'user_service', '.env')),
]
env_path = next((p for p in candidate_env_paths if os.path.exists(p)), None)
if env_path:
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"[INFO] .env 로드: {env_path}")
else:
    print("[경고] services/user_service/.env 파일을 찾지 못했습니다. 기본 환경변수를 사용합니다.")

ORACLE_USER = os.getenv('ORACLE_USER')
ORACLE_PASSWORD = os.getenv('ORACLE_PASSWORD')
ORACLE_DSN = os.getenv('ORACLE_DSN')
ORACLE_CLIENT_PATH = os.getenv('ORACLE_CLIENT_PATH')


def init_qna_schema():
    # 2) 오라클 클라이언트 초기화 (이미 초기화된 경우 무시)
    if ORACLE_CLIENT_PATH:
        try:
            cx_Oracle.init_oracle_client(lib_dir=ORACLE_CLIENT_PATH)
        except cx_Oracle.ProgrammingError as e:
            if "already been initialized" in str(e):
                pass
            else:
                raise
    else:
        print("[경고] ORACLE_CLIENT_PATH가 설정되지 않았습니다. 환경 변수를 확인하세요.")

    # 3) DB 연결
    conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=ORACLE_DSN)
    cur = conn.cursor()

    # 4) 객체 생성 (존재하면 무시)
    #QNA_POSTS: 글(제목/내용/작성자/카운트/시간)
    create_posts_table = """
      BEGIN
        EXECUTE IMMEDIATE '
        CREATE TABLE QNA_POSTS (
            ID           NUMBER        PRIMARY KEY,
            USR_ID       VARCHAR2(50)  NOT NULL,
            TITLE        VARCHAR2(200) NOT NULL,
            CONTENT      CLOB          NOT NULL,
            VIEW_COUNT   NUMBER        DEFAULT 0 NOT NULL,
            LIKE_COUNT   NUMBER        DEFAULT 0 NOT NULL,
            CREATED_AT   DATE          DEFAULT SYSDATE NOT NULL,
            UPDATED_AT   DATE          NULL,
            KIND         VARCHAR2(20)  DEFAULT ''일반'' NOT NULL,
            IS_PUBLIC    NUMBER(1)     DEFAULT 1        NOT NULL, -- 1:공개, 0:비공개
            HAS_FILE     NUMBER(1)     DEFAULT 0        NOT NULL,
            AUTHOR_NAME  VARCHAR2(100) NULL,
            EMAIL        VARCHAR2(120) NULL
        )';
    EXCEPTION WHEN OTHERS THEN NULL; END;
    """
    #시퀀스: QNA_POSTS_SEQ 
    create_posts_seq = """
    BEGIN
        EXECUTE IMMEDIATE 'CREATE SEQUENCE QNA_POSTS_SEQ START WITH 1 INCREMENT BY 1';
    EXCEPTION WHEN OTHERS THEN NULL; END;
    """
    #-- 업그레이드(이미 테이블이 있을 때 컬럼 추가)
    alter_posts = """
    BEGIN
        FOR c IN (
            SELECT column_name FROM user_tab_columns
            WHERE table_name = 'QNA_POSTS' AND column_name IN ('KIND','IS_PUBLIC','HAS_FILE','AUTHOR_NAME','EMAIL')
        ) LOOP NULL; END LOOP;
        -- KIND
        BEGIN EXECUTE IMMEDIATE 'ALTER TABLE QNA_POSTS ADD (KIND VARCHAR2(20) DEFAULT ''일반'' NOT NULL)'; EXCEPTION WHEN OTHERS THEN NULL; END;
        -- IS_PUBLIC
        BEGIN EXECUTE IMMEDIATE 'ALTER TABLE QNA_POSTS ADD (IS_PUBLIC NUMBER(1) DEFAULT 1 NOT NULL)'; EXCEPTION WHEN OTHERS THEN NULL; END;
        -- HAS_FILE
        BEGIN EXECUTE IMMEDIATE 'ALTER TABLE QNA_POSTS ADD (HAS_FILE NUMBER(1) DEFAULT 0 NOT NULL)'; EXCEPTION WHEN OTHERS THEN NULL; END;
        -- AUTHOR_NAME
        BEGIN EXECUTE IMMEDIATE 'ALTER TABLE QNA_POSTS ADD (AUTHOR_NAME VARCHAR2(100))'; EXCEPTION WHEN OTHERS THEN NULL; END;
        -- EMAIL
        BEGIN EXECUTE IMMEDIATE 'ALTER TABLE QNA_POSTS ADD (EMAIL VARCHAR2(120))'; EXCEPTION WHEN OTHERS THEN NULL; END;
    END;
    """
    create_idx_posts_usr = """
    BEGIN
        EXECUTE IMMEDIATE 'CREATE INDEX IDX_QNA_POSTS_USR ON QNA_POSTS(USR_ID)';
    EXCEPTION WHEN OTHERS THEN NULL; END;
    """
    
    #QNA_COMMENTS: 댓글 + 대댓글(POST_ID, PARENT_ID 계층)
    create_comments_table = """
    BEGIN
        EXECUTE IMMEDIATE '
        CREATE TABLE QNA_COMMENTS (
            ID          NUMBER       PRIMARY KEY,
            POST_ID     NUMBER       NOT NULL,
            USR_ID      VARCHAR2(50) NOT NULL,
            PARENT_ID   NUMBER       NULL,
            CONTENT     CLOB         NOT NULL,
            CREATED_AT  DATE         DEFAULT SYSDATE NOT NULL,
            UPDATED_AT  DATE         NULL
        )';
    EXCEPTION WHEN OTHERS THEN NULL; END;
    """

    #시퀀스: QNA_COMMENTS_SEQ
    create_comments_seq = """
    BEGIN
        EXECUTE IMMEDIATE 'CREATE SEQUENCE QNA_COMMENTS_SEQ START WITH 1 INCREMENT BY 1';
    EXCEPTION WHEN OTHERS THEN NULL; END;
    """
    
    # 인덱스
    create_idx_comments_post = """
    BEGIN
        EXECUTE IMMEDIATE 'CREATE INDEX IDX_QNA_COMMENTS_POST ON QNA_COMMENTS(POST_ID)';
    EXCEPTION WHEN OTHERS THEN NULL; END;
    """
    create_idx_comments_parent = """
    BEGIN
        EXECUTE IMMEDIATE 'CREATE INDEX IDX_QNA_COMMENTS_PARENT ON QNA_COMMENTS(PARENT_ID)';
    EXCEPTION WHEN OTHERS THEN NULL; END;
    """
    

    # FK (ON DELETE CASCADE)
    fk_comments_post = """
    BEGIN
        EXECUTE IMMEDIATE '
            ALTER TABLE QNA_COMMENTS
            ADD CONSTRAINT FK_QNA_COMMENTS_POST
            FOREIGN KEY (POST_ID) REFERENCES QNA_POSTS(ID) ON DELETE CASCADE
        ';
    EXCEPTION WHEN OTHERS THEN NULL; END;
    """
    fk_comments_parent = """
    BEGIN
        EXECUTE IMMEDIATE '
            ALTER TABLE QNA_COMMENTS
            ADD CONSTRAINT FK_QNA_COMMENTS_PARENT
            FOREIGN KEY (PARENT_ID) REFERENCES QNA_COMMENTS(ID) ON DELETE CASCADE
        ';
    EXCEPTION WHEN OTHERS THEN NULL; END;
    """

    #시퀀스: 첨부 전용 QNA_FILES_SEQ
    create_files_table = """
    BEGIN
        EXECUTE IMMEDIATE '
        CREATE TABLE QNA_FILES (
            ID           NUMBER         PRIMARY KEY,
            POST_ID      NUMBER         NOT NULL,
            ORIG_NAME    VARCHAR2(255)  NOT NULL,
            STORED_NAME  VARCHAR2(255)  NOT NULL,
            MIME         VARCHAR2(100)  NULL,
            FILE_SIZE    NUMBER         NULL,
            PATH         VARCHAR2(400)  NOT NULL,
            CREATED_AT   DATE           DEFAULT SYSDATE NOT NULL
        )';
    EXCEPTION WHEN OTHERS THEN NULL; END;
    """
    create_files_seq = """
    BEGIN
        EXECUTE IMMEDIATE 'CREATE SEQUENCE QNA_FILES_SEQ START WITH 1 INCREMENT BY 1';
    EXCEPTION WHEN OTHERS THEN NULL; END;
    """
    create_idx_files_post = """
    BEGIN
        EXECUTE IMMEDIATE 'CREATE INDEX IDX_QNA_FILES_POST ON QNA_FILES(POST_ID)';
    EXCEPTION WHEN OTHERS THEN NULL; END;
    """
    fk_files_post = """
    BEGIN
        EXECUTE IMMEDIATE '
            ALTER TABLE QNA_FILES
            ADD CONSTRAINT FK_QNA_FILES_POST
            FOREIGN KEY (POST_ID) REFERENCES QNA_POSTS(ID) ON DELETE CASCADE
        ';
    EXCEPTION WHEN OTHERS THEN NULL; END;
    """
    try:
        cur.execute(create_posts_table)
        cur.execute(create_posts_seq)
        cur.execute(alter_posts)
        cur.execute(create_idx_posts_usr)
        
        cur.execute(create_comments_table)
        cur.execute(create_comments_seq)
        cur.execute(create_idx_comments_post)
        cur.execute(create_idx_comments_parent)
        cur.execute(fk_comments_post)
        cur.execute(fk_comments_parent)

        cur.execute(create_files_table)
        cur.execute(create_files_seq)
        cur.execute(create_idx_files_post)
        cur.execute(fk_files_post)
        
        conn.commit()
        print("✅ Q&A 스키마 생성/확인 완료")
    except Exception as e:
        print("❌ 오류 발생:", e)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    init_qna_schema()
