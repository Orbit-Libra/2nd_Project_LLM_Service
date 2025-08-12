## 2차 프로젝트 - 딥러닝 & 플라스크 기반 서비스 프로젝트

### 프로젝트 명 : Generative AI 및 지능형 에이전트 기반 교육 인프라 예측 서비스

### 5조 - 강승민, 김선희

## 디렉토리 구조

```

2nd_Project_LLM_Service/
│  
├── .venv/                     # 가상환경 폴더
├── app/                       # 플라스크 웹서버 게이트웨이
├── docs/                      # 문서 폴더
├── services/                  # 각 서비스 폴더
├── tools/                     # 프로젝트 프로그램파일 폴더
├── flaskrun-data.bat          # 플라스크 데이터서버 실행 스크립트
├── flaskrun-predict.bat       # 플라스크 예측서버 실행 스크립트
├── flaskrun-web.bat           # 플라스크 웹서버 실행 스크립트
├── requirements.txt           # 라이브러리 목록
├── setup-env.bat              # 가상환경 & DB 셋업 스크립트
└── setup-pipeline.bat         # 머신러닝 초기 데이터 셋업 스크립트

```

## 패키지 구동 방법

#### 1. 환경세팅

사용 파이썬 버전 : 3.11.9

오라클 DB 사용 버전 : 

오라클 클라이언트 버전 : 

#### 2. 초기환경 세팅

setup-env 실행 : 가상환경 및 오라클 테이블 스페이스 및 스키마, 초기 테이블 생성

setup-pipline 실행 : 서비스용 초기 전처리 및 머신러닝 예측 전체 진행


#### 3. 플라스크 서버 실행

flaskrun 3종 실행 : 웹서버 및 2종의 api 서버 실행

관리자 계정으로 로그인 : ID : libra_admin, PW : 1234

관리자 페이지 접속 후 데이터 초기 동기화 실행


## 프로젝트 전체 디렉토리 정보


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
│   │   ├── api/       # 플라스크 api
│   │   │   │  
│   │   │   ├── data_api.py  
│   │   │   ├── main.py  
│   │   │   └── num06_api.py  
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
│   │   │
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
│   │   ├── api/               # 플라스크 api
│   │   │   │  
│   │   │   ├── server.py  
│   │   │   └── user_api.py  
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
│   ├── user_service/          # 유저 서비스 관련 라우터
│   │   │
│   │   ├── db/
│   │   │   │
│   │   │   └── USER_DB.DBF    # 유저 데이터베이스
│   │   │
│   │   ├── .env 
│   │   ├── init_oracle_user_data.py 
│   │   ├── login_manager.py
│   │   ├── predict_sync.py
│   │   └── user_analysis.py
│   │
│   ├── web_frontend/          # 사용자 웹 프론트엔드
│   │   │
│   │   ├── api/               # 플라스크 웹서버 라우터
│   │   │   │  
│   │   │   ├── admin_system.py
│   │   │   ├── chart_data.py
│   │   │   ├── Oracle_utils.py
│   │   │   ├── profile_api.py
│   │   │   ├── register_api.py
│   │   │   ├── sync.py
│   │   │   └── user_api.py
│   │   │
│   │   ├── static/
│   │   │   │
│   │   │   ├── css/
│   │   │   │   │
│   │   │   │   ├── common/
│   │   │   │   │   │
│   │   │   │   │   └── header-footer.css
│   │   │   │   │
│   │   │   │   ├── admin.css
│   │   │   │   ├── chartpage1.css
│   │   │   │   ├── login.css
│   │   │   │   ├── main.css
│   │   │   │   └── profile.css
│   │   │   │
│   │   │   │
│   │   │   ├── images/
│   │   │   │   |
│   │   │   │   ├── logo.jpeg
│   │   │   │   └── logo2.png
│   │   │   │
│   │   │   │
│   │   │   └── js/  
│   │   │       |
│   │   │       ├── admin.js
│   │   │       ├── chartpage1.js
│   │   │       ├── chartpage2.js
│   │   │       ├── header.js
│   │   │       ├── main.js
│   │   │       ├── profile.js
│   │   │       ├── register.js
│   │   │       └── userservice.js
│   │   │
│   │   ├── templates/
│   │   │   │
│   │   │   ├── common/
│   │   │   │   |
│   │   │   │   ├── chatbot.html
│   │   │   │   ├── footer.html
│   │   │   │   └── header.html
│   │   │   │
│   │   │   ├── admin.html
│   │   │   ├── chartpage1.html
│   │   │   ├── chartpage2.html
│   │   │   ├── login.html
│   │   │   ├── main.html
│   │   │   ├── profile.html
│   │   │   ├── register.html
│   │   │   └── userservice.html
│   │   │
│   │   └── .env 
│   │
│   ├── llm_service/           # LLM 챗봇 서비스
│   │
│   └── tools/                 # 필수유틸 폴더
│       │
│       └── instantclient-basic-windows.x64-19.25.0.0.0dbru/
│
│
├── flaskrun-data.bat          # 플라스크 데이터서버 실행 스크립트
├── flaskrun-predict.bat       # 플라스크 예측서버 실행 스크립트
├── flaskrun-web.bat           # 플라스크 웹서버 실행 스크립트
├── requirements.txt           # 라이브러리 목록
├── setup-env.bat              # 가상환경 & DB 셋업 스크립트
└── setup-pipeline.bat         # 머신러닝 초기 데이터 셋업 스크립트

```