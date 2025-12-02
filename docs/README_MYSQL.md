# MySQL 설치 및 사용 가이드

이 문서는 MySQL을 처음 사용하는 사람을 위한 가이드입니다.

## 📌 목차
1. [MySQL 설치](#1-mysql-설치)
2. [MySQL 실행 및 접속](#2-mysql-실행-및-접속)
3. [데이터베이스 및 테이블 생성](#3-데이터베이스-및-테이블-생성)
4. [Python 라이브러리 설치](#4-python-라이브러리-설치)
5. [코드 사용법](#5-코드-사용법)

---

## 1. MySQL 설치

### Linux (Ubuntu/Debian)
```bash
# MySQL 서버 설치
sudo apt update
sudo apt install mysql-server

# MySQL 보안 설정 (선택사항)
sudo mysql_secure_installation
```

### macOS
```bash
# Homebrew로 설치
brew install mysql

# MySQL 서비스 시작
brew services start mysql
```

### Windows
1. [MySQL 공식 사이트](https://dev.mysql.com/downloads/installer/)에서 MySQL Installer 다운로드
2. 설치 프로그램 실행
3. "Developer Default" 또는 "Server only" 선택
4. root 비밀번호 설정 (꼭 기억하세요!)

---

## 2. MySQL 실행 및 접속

### MySQL 서비스 시작

**Linux:**
```bash
sudo systemctl start mysql
sudo systemctl enable mysql  # 부팅시 자동 시작
```

**macOS:**
```bash
brew services start mysql
```

**Windows:**
- 서비스 앱에서 "MySQL80" 서비스 시작
- 또는 설치시 자동으로 시작됨

### MySQL 접속

터미널(또는 CMD)에서 다음 명령어로 접속:

```bash
mysql -u root -p
```

- `-u root`: root 사용자로 접속
- `-p`: 비밀번호 입력 (Enter 후 비밀번호 입력)

**비밀번호를 설정하지 않았다면:**
```bash
mysql -u root
```

---

## 3. 데이터베이스 및 테이블 생성

MySQL에 접속한 후, 다음 SQL 명령어들을 **순서대로** 실행하세요.

### 3-1. 데이터베이스 생성

```sql
-- 데이터베이스 생성
CREATE DATABASE coin_alarm;

-- 생성된 데이터베이스 확인
SHOW DATABASES;

-- 데이터베이스 선택
USE coin_alarm;
```

### 3-2. 캔들 데이터 테이블 생성

```sql
-- candles 테이블 생성
CREATE TABLE candles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open_time DATETIME NOT NULL,
    open_price DECIMAL(20, 8) NOT NULL,
    high_price DECIMAL(20, 8) NOT NULL,
    low_price DECIMAL(20, 8) NOT NULL,
    close_price DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 8) NOT NULL,
    close_time DATETIME NOT NULL,
    quote_volume DECIMAL(20, 8),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_candle (symbol, timeframe, open_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3-3. 인덱스 추가 (검색 속도 향상)

```sql
-- 빠른 조회를 위한 인덱스 생성
CREATE INDEX idx_symbol_timeframe ON candles(symbol, timeframe);
CREATE INDEX idx_open_time ON candles(open_time);
```

### 3-4. 테이블 확인

```sql
-- 테이블이 제대로 생성되었는지 확인
SHOW TABLES;

-- 테이블 구조 확인
DESCRIBE candles;
```

### 3-5. MySQL 종료

```sql
-- MySQL 접속 종료
EXIT;
```

---

## 4. Python 라이브러리 설치

MySQL을 Python에서 사용하려면 `mysql-connector-python` 라이브러리가 필요합니다.

```bash
pip install mysql-connector-python
```

또는 requirements.txt에 추가:
```
mysql-connector-python==8.0.33
python-binance
```

설치 확인:
```bash
python -c "import mysql.connector; print('MySQL 연결 라이브러리 설치 완료!')"
```

---

## 5. 코드 사용법

### 5-1. 기본 사용 예제

`example.py` 파일을 참고하세요. 간단한 예:

```python
from downloader import ChartDownloader

# DB 연결 정보 설정
db_config = {
    'host': 'localhost',      # MySQL 서버 주소
    'user': 'root',           # MySQL 사용자 이름
    'password': '1234',       # MySQL 비밀번호 (본인이 설정한 것)
    'database': 'coin_alarm'  # 사용할 데이터베이스 이름
}

# ChartDownloader 생성
downloader = ChartDownloader(db_config)

# 데이터 다운로드 및 저장
downloader.download_and_save('BTCUSDT', '1h', initial_limit=1000)

# DB에서 데이터 조회
candles = downloader.get_candles_from_db('BTCUSDT', '1h', limit=100)
print(f"조회된 캔들 개수: {len(candles)}")

# 연결 종료
downloader.close()
```

### 5-2. 주의사항

1. **비밀번호**: 코드에 비밀번호를 직접 쓰지 말고, 환경 변수나 별도 설정 파일 사용 권장
2. **첫 실행**: 처음에는 `initial_limit`을 크게 설정 (1000~1500)
3. **업데이트**: 두 번째 실행부터는 자동으로 최신 데이터만 다운로드
4. **연결 종료**: 사용 후 꼭 `downloader.close()` 호출

### 5-3. 데이터 확인

MySQL에서 직접 데이터를 확인하려면:

```bash
mysql -u root -p
```

```sql
USE coin_alarm;

-- 저장된 데이터 개수 확인
SELECT symbol, timeframe, COUNT(*) as count 
FROM candles 
GROUP BY symbol, timeframe;

-- 최근 10개 캔들 조회
SELECT * FROM candles 
WHERE symbol = 'BTCUSDT' AND timeframe = '1h' 
ORDER BY open_time DESC 
LIMIT 10;
```

---

## 🔧 문제 해결

### 1. MySQL 접속 오류
```
ERROR 1045 (28000): Access denied for user 'root'@'localhost'
```
**해결방법:**
- 비밀번호가 틀렸거나 설정되지 않았습니다
- Linux: `sudo mysql`로 접속 후 비밀번호 재설정

### 2. 데이터베이스 연결 오류
```python
mysql.connector.errors.ProgrammingError: Unknown database 'coin_alarm'
```
**해결방법:**
- 데이터베이스가 생성되지 않았습니다
- "3. 데이터베이스 및 테이블 생성" 섹션 참고

### 3. 테이블이 없다는 오류
```
Table 'coin_alarm.candles' doesn't exist
```
**해결방법:**
- candles 테이블을 생성하지 않았습니다
- "3-2. 캔들 데이터 테이블 생성" 섹션 참고

---

## 📚 추가 학습 자료

- [MySQL 공식 문서](https://dev.mysql.com/doc/)
- [Python MySQL 튜토리얼](https://www.w3schools.com/python/python_mysql_getstarted.asp)

---

## ✅ 체크리스트

설정이 완료되었는지 확인:

- [ ] MySQL 설치 완료
- [ ] MySQL 서비스 실행 중
- [ ] `coin_alarm` 데이터베이스 생성
- [ ] `candles` 테이블 생성
- [ ] `mysql-connector-python` 설치
- [ ] DB 연결 정보 (host, user, password) 확인
- [ ] `example.py` 실행 성공

모두 완료했다면 이제 사용할 준비가 되었습니다! 🎉
