# 코인 거래량 급증 모니터링 시스템

## 🚀 실행 방법

### 1. 필요한 라이브러리 설치

```bash
pip install fastapi uvicorn apscheduler
```

### 2. DB 설정

`api_server.py` 파일에서 본인의 MySQL 정보로 수정:

```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234',  # 본인 비밀번호로 변경
    'database': 'coin_alarm'
}
```

### 3. 서버 실행

```bash
python api_server.py
```

### 4. 웹 브라우저에서 확인

```
http://localhost:8000
```

---

## 📊 동작 방식

1. **자동 스캔**: 매 5분마다 자동으로 거래량 급증 체크
2. **4가지 시간봉 확인**: 5분, 15분, 30분, 1시간봉 모두 체크
3. **결과 저장**: `surge_results.json` 파일에 저장
4. **웹에서 확인**: 실시간으로 웹페이지에서 확인 가능

---

## 🌐 API 엔드포인트

### 메인 페이지
```
GET http://localhost:8000/
```
- 거래량 급증 종목을 보기 좋게 표시
- 30초마다 자동 새로고침

### JSON API
```
GET http://localhost:8000/api/surge
```
- JSON 형식으로 데이터 반환
- 다른 프로그램에서 활용 가능

---

## 📝 파일 설명

### `api_server.py`
- **FastAPI 서버**: 웹 API 제공
- **스케줄러**: 5분마다 자동 실행
- **스캔 함수**: 모든 USDT 심볼 체크
- **HTML 페이지**: 결과 표시

### `surge_results.json`
- 최신 스캔 결과 저장
- 서버 재시작해도 유지됨

```json
{
  "last_update": "2025-11-09 15:30:00",
  "surge_coins": [
    {
      "timeframe": "5m",
      "count": 3,
      "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    },
    {
      "timeframe": "1h",
      "count": 5,
      "symbols": ["ADAUSDT", "SOLUSDT", ...]
    }
  ]
}
```

---

## 🎯 설정 변경

### 스캔 주기 변경
```python
# api_server.py의 start_scheduler() 함수에서
scheduler.add_job(scan_volume_surge, 'interval', minutes=5)  # 5분 → 원하는 값
```

### 거래량 임계값 변경
```python
# scan_volume_surge() 함수에서
surge_symbols = filter_obj.filtering_symbols(
    ...
    threshold=2.0,  # 2.0 → 원하는 배수
    ...
)
```

### 시간봉 변경
```python
# scan_volume_surge() 함수에서
timeframes = ['5m', '15m', '30m', '1h']  # 원하는 시간봉 추가/제거
```

---

## 💡 사용 예시

### 1. 웹에서 확인
- 브라우저로 `http://localhost:8000` 접속
- 거래량 급증 종목 실시간 확인
- 자동으로 30초마다 새로고침

### 2. API로 데이터 가져오기
```python
import requests

response = requests.get('http://localhost:8000/api/surge')
data = response.json()

print(f"마지막 업데이트: {data['last_update']}")
for item in data['surge_coins']:
    print(f"{item['timeframe']}: {item['symbols']}")
```

### 3. 파일에서 직접 읽기
```python
import json

with open('surge_results.json', 'r') as f:
    data = json.load(f)
    print(data)
```

---

## 🔧 문제 해결

### 포트 충돌
```bash
# 다른 포트 사용
uvicorn api_server:app --host 0.0.0.0 --port 8080
```

### 스캔이 안 됨
- DB 연결 확인
- 심볼 데이터가 DB에 있는지 확인
- 로그 메시지 확인

---

## 📌 주의사항

1. 첫 실행 시 모든 심볼 데이터를 다운로드하므로 시간이 걸릴 수 있음
2. 바이낸스 API 제한이 있으므로 너무 많은 심볼을 동시에 확인하면 에러 발생 가능
3. 서버가 계속 실행되어야 5분마다 자동 스캔됨

---

## ✅ 완료!

서버를 실행하고 웹브라우저로 확인하세요! 🎉
