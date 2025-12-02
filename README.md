# CoinAlarm - 거래량 급증 모니터링 시스템

바이낸스 선물 거래소의 코인 거래량을 실시간 모니터링하고 급증 종목을 찾아내는 시스템

## 📁 프로젝트 구조

```
CoinAlarm/
├── main.py                 # 🚀 메인 실행 파일
│
├── core/                   # 핵심 로직
│   ├── database.py         # MySQL DB 관리
│   ├── downloader.py       # 바이낸스 데이터 다운로드
│   └── scanner.py          # 거래량 급증 스캔
│
├── service/                # 비즈니스 로직
│   └── filter.py           # 거래량 급증 필터
│
├── api/                    # API 서버
│   ├── api_server.py       # FastAPI 서버
│   └── templates/          # HTML 템플릿
│       └── index.html
│
├── data/                   # 데이터 저장
│   └── surge_results.json  # 스캔 결과
│
├── tests/                  # 테스트 파일
│   └── test.py
│
└── docs/                   # 문서
    ├── README_API.md
    └── README_MYSQL.md
```

---

## 🚀 빠른 시작

### 1. 필요한 라이브러리 설치

```bash
pip install fastapi uvicorn apscheduler python-binance mysql-connector-python
```

### 2. MySQL 설정

`docs/README_MYSQL.md` 참고하여 MySQL 설치 및 DB 생성

### 3. DB 설정 수정

`api/api_server.py`에서 본인의 MySQL 정보로 수정:

```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '본인_비밀번호',
    'database': 'coin_alarm'
}
```

### 4. 서버 실행

```bash
python main.py
```

### 5. 웹 브라우저에서 확인

```
http://localhost:8000
```

---

## 📖 자세한 문서

- **API 사용법**: `docs/README_API.md`
- **MySQL 설정**: `docs/README_MYSQL.md`

---

## 💡 주요 기능

- ✅ 매 5분마다 자동 스캔
- ✅ 4가지 시간봉 분석 (5m, 15m, 30m, 1h)
- ✅ 300+ USDT 선물 심볼 모니터링
- ✅ 웹 UI로 실시간 확인
- ✅ REST API 제공

---

## 🎯 사용 예시

### 웹에서 확인
```
http://localhost:8000
```

### API로 데이터 가져오기
```python
import requests

response = requests.get('http://localhost:8000/api/surge')
data = response.json()
print(data)
```

---

## 📝 라이센스

교육 목적 프로젝트
# CoinAlarm
