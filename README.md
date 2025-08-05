### 2nd_Project_LLM_Service

```

2nd_Project_LLM_Service/
│  
├── docs/ <- 문서폴더
│   │
│   └── devlogs/    
│
├── services/                  # 모든 마이크로서비스 폴더 묶음
│   │
│   ├── gateway/               # API 게이트웨이
│   ├── user_service/          # 유저 관련 기능
│   ├── prediction_service/    # 머신러닝 예측 서비스
│   ├── data_service/          # 데이터 수집 및 처리 서비스
│   ├── ml_service/            # 모델 학습 및 튜닝
│   ├── web_frontend/          # 사용자 웹 프론트엔드
│   └── llm_service/           # LLM 챗봇 서비스
│
├── shared_libs/               # 공통 유틸리티
├── .env                       # 환경 변수
├── setup.bat                  # 가상환경 & DB 셋업 스크립트
└── README.md


```


### 가상환경 및 테이블스페이스 세팅

1. 루트 경로에서 터미널 실행 및 setup.bat 실행
-> cd 경로/2nd_Project_LLM_Service
-> ./setup.bat