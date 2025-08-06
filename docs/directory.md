```

2nd_Project_LLM_Service/
│  
├── .venv/ <- 가상환경 폴더
│   │
│   └── libra_env/    
│  
├── app/ <- 플라스크 서버 시작지점
│   │
│   ├── __init__.py  
│   └── main.py
│  
├── docs/ <- 문서 폴더
│   │
│   └── devlogs/    
│
├── services/                  # 모든 마이크로서비스 폴더 묶음
│   │
│   ├── core_utiles/                        # 공통 모듈 전용 폴더
│   │   ├── __init__.py
│   │   ├── config_loader.py                # .env 로드 모듈
│   │   ├── Mapper.py                       # 헤더, 대학명 매핑표 모듈
│   │   ├── OracleDBConnection.py           # 오라클DBD 접속 모듈
│   │   ├── OracleSchemaBuilder.py          # 테이블 생성 시 데이터타입 보정 모듈
│   │   └── OracleTableCreater.py           # 보정 후 테이블 생성 모듈
│   │   
│   │
│   ├── data_service/          # 데이터 수집 및 처리 서비스
│   │   │
│   │   ├── DataHandling/       # 원본파일 CSV파일화 및 DB 업로드 패키지  
│   │   │   │  
│   │   │   ├── __init__.py  
│   │   │   ├── __main__.py                  # DataHandling 패키지 실행  
│   │   │   ├── CSVHeaderRenamer.py          # 모든 컬럼 헤더 변경 클래스  
│   │   │   ├── CSVToOracleUploader.py       # 테이블 생성 클래스  
│   │   │   ├── CWURCrawler.py               # 대학 평가점수 크롤링 클래스  
│   │   │   ├── EnNameCollector.py           # 영문 대학명 리스트화 클래스  
│   │   │   ├── ExcelToCSVConverter_ver1.py  # CSV파일 변환 클래스 1  
│   │   │   ├── ExcelToCSVConverter_ver2.py  # CSV파일 변환 클래스 2  
│   │   │   ├── HeaderAbbreviationMapper.py  # 헤더 한글 영문 매핑 클래스  
│   │   │   ├── HeaderTermCollector.py       # 모든 csv파일 컬럼 별 헤더 수집 클래스  
│   │   │   ├── NameMapper.py                # 영문 대학명 한국명으로 매핑 클래스  
│   │   │   └── RankedScoreExporter.py       # 연도 별 대학 평가점수 csv 파일 생성  
│   │   │  
│   │   ├── DBHandling/                      # DB테이블 전처리 및 정규화 패키지  
│   │   │   │  
│   │   │   ├── __init__.py  
│   │   │   ├── __main__.py                  # DBHandling 패키지 실행  
│   │   │   ├── DataMergerAndExporter.py     # 병합 테이블 생성 클래스  
│   │   │   ├── FilteredScoreUploader.py     # 정규화 테이블 생성 클래스  
│   │   │   └── TableMergerUploader.py       # 데이터 병합 및 테이블 생성 클래스
│   │   │
│   │   ├── db/
│   │   │   │
│   │   │   └── DATA_DB.DBF    # AI용 데이터베이스
│   │   |
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   └── .env
│   │
│   ├── ml_service/            # 모델 학습 및 튜닝
│   │   │
│   │   ├── _Configs/
│   │   │   │
│   │   │   └── Num01_Config_XGB.json
│   │   │
│   │   ├── _Logs/
│   │   │   │
│   │   │   └── Num01_XGB_v1.0_Log.json
│   │   │
│   │   ├── _Models/
│   │   │   │
│   │   │   └── Num01_XGB_full_v1.0.pkl
│   │   │
│   │   ├── ModelCreator/
│   │   │   │
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py
│   │   │   ├── Cleaner.py
│   │   │   ├── Controller_Num01.py
│   │   │   ├── Controller_Num02.py
│   │   │   ├── Fetcher.py
│   │   │   ├── Handler.py
│   │   │   ├── Logger.py
│   │   │   ├── ModelLoader.py
│   │   │   └── Trainer.py
│   │   │
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   └── .env
│   │
│   ├── prediction_service/    # 머신러닝 예측 서비스
│   │   │
│   │   ├── Predictor/
│   │   │   │
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py
│   │   │   ├── Controller.py
│   │   │   ├── PickleLoader.py
│   │   │   ├── TableBuilder_Num01.py
│   │   │   ├── TableBuilder_Num02.py
│   │   │   └── TableBuilder_User.py
│   │   │
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   └── .env
│   │
│   ├── user_service/          # 유저 관련 기능
│   │   │
│   │   ├── db/
│   │   │   │
│   │   │   └── USER_DB.DBF    # 유저 데이터베이스
│   │
│   ├── web_frontend/          # 사용자 웹 프론트엔드
│   │   │
│   │   ├── db/
│   │   │   │
│   │   │   └── WEB_DB.DBF     # 웹페이지 데이터베이스
│   │   │
│   │   ├── static/
│   │   │   │
│   │   │   ├── css/
│   │   │   ├── images/
│   │   │   └── js/             
│   │   │
│   │   ├── templates/
│   │   │   │
│   │   │   ├── footer.html
│   │   │   ├── header.html
│   │   │   ├── index.html
│   │   │   └── main.html     
│   │
│   └── llm_service/           # LLM 챗봇 서비스
│
├── .env                       # 종합 환경 변수
├── flaskrun.bat               # 플라스크 서버 실행 스크립트
├── requirements.txt           # 라이브러리 목록
└── setup.bat                  # 가상환경 & DB 셋업 스크립트

```

USR_CR
USR_ID
USR_PW 
USR_NAME
USR_SNM
1ST_YR,1ST_USR_CPS,1ST_USR_LPS,1ST_USR_VPS,2ND_YR,2ND_USR_CPS,2ND_USR_LPS,2ND_USR_VPS,3RD_YR,3RD_USR_CPS,3RD_USR_LPS,3RD_USR_VPS,4TH_YR,4TH_USR_CPS,4TH_USR_LPS,4TH_USR_VPS,SCR_EST_1ST,SCR_EST_2ND,SCR_EST_3RD,SCR_EST_4TH

