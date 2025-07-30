## 디렉토리 구조

```

services/
│
├── gateway/                    # API 게이트웨이 (Flask API Gateway)
│   ├── app.py
│   ├── routes/
│   ├── utils/
│   └── Dockerfile
│
├── user_service/              # 회원가입/로그인/유저 데이터 관리
│   ├── app/
│   │   ├── controllers/
│   │   ├── models/
│   │   ├── services/
│   │   ├── utils/
│   │   └── __init__.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── prediction_service/        # ML 모델 기반 예측 및 비교 분석
│   ├── models/                # .pkl 모델 저장 및 로딩
│   ├── app/
│   │   ├── inference.py
│   │   ├── controller.py
│   │   └── utils.py
│   ├── config/
│   ├── logs/
│   └── Dockerfile
│
├── data_service/              # 대학 도서관 DB, 통계 & 외부 크롤링 데이터 관리
│   ├── crawler/
│   ├── transformer/
│   ├── uploader/
│   ├── database/
│   │   ├── schema/
│   │   └── connection/
│   ├── app/
│   └── Dockerfile
│
├── ml_service/       # 주기적 모델 학습 및 튜닝
│   ├── trainer/
│   ├── tuner/
│   ├── config/
│   ├── logs/
│   ├── pkl_export/
│   └── Dockerfile
│
├── web_frontend/              # 사용자용 웹페이지 (HTML, CSS, JS + 챗봇)
│   ├── static/
│   ├── templates/
│   ├── chatbot/
│   ├── charts/
│   ├── app.py
│   └── Dockerfile
│
├── llm_service/               # LLM 연동 챗봇 (추후 확장)
│   ├── agent/
│   ├── prompts/
│   ├── core/
│   └── Dockerfile
│
├── docker-compose.yml         # 전체 MSA 서비스 통합 및 오케스트레이션
└── README.md


```