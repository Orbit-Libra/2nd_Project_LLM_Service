### 2nd_Project_LLM_Service

```

2nd_Project_LLM_Service/
│  
├── \docs <- 문서폴더
│   │
│   ├── devlogs/    
│
├── services/                  # 모든 마이크로서비스 폴더 묶음
│   │
│   ├── gateway/               # API 게이트웨이
│   ├── user_service/          # 유저 관련 기능
│   ├── prediction_service/    # 머신러닝 예측 서비스
│   ├── data_service/          # 데이터 수집 및 처리 서비스
│   ├── ml_training_service/   # 모델 학습 및 튜닝
│   ├── web_frontend/          # 사용자 웹 프론트엔드
│   └── llm_service/           # LLM 챗봇 서비스
│
├── shared_libs/               # 공통 유틸리티
├── .env                       # 환경 변수
├── docker-compose.yml         # 전체 컨테이너 오케스트레이션
└── README.md


```