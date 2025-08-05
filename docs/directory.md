```

2nd_Project_LLM_Service/
│  
├── .venv/ <- 가상환경 폴더
│   │
│   └── libra_env/    
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
│   │   ├── OracleDBConnection.py           # 오라클DB 접속 모듈
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
│   │
│   │
│   │
│   ├── ml_service/            # 모델 학습 및 튜닝
│   │
│   ├── prediction_service/    # 머신러닝 예측 서비스
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
│   │
│   └── llm_service/           # LLM 챗봇 서비스
│
├── .env                       # 종합 환경 변수
├── setup.bat                  # 가상환경 & DB 셋업 스크립트
└── README.md

```




http://www.rinfo.kr/stat/search/basic/1/result?sm=basic&syf=2014&syt=2024&year=2014%2C2015%2C2016%2C2017%2C2018%2C2019%2C2020%2C2021%2C2022%2C2023%2C2024&st=UNI&ut=&us=&etcheckall=&rgcheckall=&su=1&oatcheckall=true&oitcheckall=true&oixcheckall=true&cpp=10

http://www.rinfo.kr/stat/search/basic/2/result?sm=basic&syf=2013&syt=2024&year=2013%2C2014%2C2015%2C2016%2C2017%2C2018%2C2019%2C2020%2C2021%2C2022%2C2023%2C2024&st=UNI&ut=&us=&etcheckall=&rgcheckall=&su=2&oatcheckall=true&oitcheckall=true&oixcheckall=true&cpp=10

http://www.rinfo.kr/stat/search/basic/5/result?sm=basic&syf=2014&syt=2024&year=2014%2C2015%2C2016%2C2017%2C2018%2C2019%2C2020%2C2021%2C2022%2C2023%2C2024&st=UNI&ut=&us=&etcheckall=&rgcheckall=&su=5&oatcheckall=true&oitcheckall=true&oixcheckall=true&cpp=10