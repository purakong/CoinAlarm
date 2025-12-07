import mysql.connector
from datetime import datetime


class CandleDatabase:
    """
    MySQL에 캔들 데이터를 저장하고 조회하는 클래스
    
    사용 방법:
    1. MySQL 서버가 실행중이어야 합니다
    2. 데이터베이스와 테이블이 생성되어 있어야 합니다 (README_MYSQL.md 참고)
    3. host, user, password, database 정보를 입력해서 연결합니다
    """
    
    def __init__(self, host='localhost', user='root', password='1234', database='coin_chart'):
        """
        MySQL 데이터베이스에 연결
        
        Args:
            host: MySQL 서버 주소 (기본값: localhost)
            user: MySQL 사용자 이름 (기본값: root)
            password: MySQL 비밀번호
            database: 사용할 데이터베이스 이름 (기본값: coin_chart)
        """
        self.connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        self.cursor = self.connection.cursor()
        print(f"✅ MySQL 데이터베이스 '{database}'에 연결되었습니다.")
    
    def save_candles(self, symbol, timeframe, klines):
        """
        캔들 데이터를 DB에 저장
        이미 존재하는 데이터는 업데이트, 없으면 새로 삽입
        
        Args:
            symbol: 거래쌍 (예: 'BTCUSDT')
            timeframe: 시간봉 (예: '1h', '5m')
            klines: 바이낸스에서 받은 캔들 데이터 리스트
        """
        insert_query = """
        INSERT INTO candles 
        (symbol, timeframe, open_time, open_price, high_price, low_price, close_price, 
         volume, close_time, quote_volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            open_price = VALUES(open_price),
            high_price = VALUES(high_price),
            low_price = VALUES(low_price),
            close_price = VALUES(close_price),
            volume = VALUES(volume),
            close_time = VALUES(close_time),
            quote_volume = VALUES(quote_volume)
        """
        
        saved_count = 0
        for kline in klines:
            # 밀리초를 초로 변환 후 datetime 객체로 변환
            open_time = datetime.utcfromtimestamp(int(kline[0]) / 1000)
            close_time = datetime.utcfromtimestamp(int(kline[6]) / 1000)
            
            values = (
                symbol,
                timeframe,
                open_time,
                float(kline[1]),  # 시가
                float(kline[2]),  # 고가
                float(kline[3]),  # 저가
                float(kline[4]),  # 종가
                float(kline[5]),  # 거래량
                close_time,
                float(kline[7])   # 거래대금
            )
            
            self.cursor.execute(insert_query, values)
            saved_count += 1
        
        self.connection.commit()
        return saved_count
    
    def get_latest_candle_time(self, symbol, timeframe):
        """
        DB에 저장된 특정 심볼의 가장 최신 캔들 시간을 조회
        
        Args:
            symbol: 거래쌍 (예: 'BTCUSDT')
            timeframe: 시간봉 (예: '1h', '5m')
        
        Returns:
            가장 최신 캔들의 open_time (datetime 객체), 없으면 None
        """
        query = """
        SELECT open_time 
        FROM candles 
        WHERE symbol = %s AND timeframe = %s 
        ORDER BY open_time DESC 
        LIMIT 1
        """
        
        self.cursor.execute(query, (symbol, timeframe))
        result = self.cursor.fetchone()
        
        if result:
            return result[0]  # datetime 객체
        return None
    
    def get_candles(self, symbol, timeframe, limit=100):
        """
        DB에서 캔들 데이터를 조회 (최신순)
        
        Args:
            symbol: 거래쌍 (예: 'BTCUSDT')
            timeframe: 시간봉 (예: '1h', '5m')
            limit: 조회할 캔들 개수 (기본값: 100)
        
        Returns:
            캔들 데이터 리스트 [(open_time, open, high, low, close, volume), ...]
        """
        query = """
        SELECT open_time, open_price, high_price, low_price, close_price, volume, quote_volume
        FROM candles 
        WHERE symbol = %s AND timeframe = %s 
        ORDER BY open_time DESC 
        LIMIT %s
        """
        
        self.cursor.execute(query, (symbol, timeframe, limit))
        results = self.cursor.fetchall()
        
        # 시간순으로 정렬 (오래된 것부터)
        return results
    
    def check_symbol_exists(self, symbol, timeframe):
        """
        DB에 특정 심볼의 데이터가 있는지 확인
        
        Args:
            symbol: 거래쌍 (예: 'BTCUSDT')
            timeframe: 시간봉 (예: '1h', '5m')
        
        Returns:
            True: 데이터 있음, False: 데이터 없음
        """
        query = """
        SELECT COUNT(*) 
        FROM candles 
        WHERE symbol = %s AND timeframe = %s
        """
        
        self.cursor.execute(query, (symbol, timeframe))
        count = self.cursor.fetchone()[0]
        return count > 0
    
    def get_data_count(self, symbol, timeframe):
        """
        DB에 저장된 특정 심볼의 캔들 개수 조회
        
        Args:
            symbol: 거래쌍 (예: 'BTCUSDT')
            timeframe: 시간봉 (예: '1h', '5m')
        
        Returns:
            저장된 캔들 개수
        """
        query = """
        SELECT COUNT(*) 
        FROM candles 
        WHERE symbol = %s AND timeframe = %s
        """
        
        self.cursor.execute(query, (symbol, timeframe))
        count = self.cursor.fetchone()[0]
        return count
    
    def delete_old_candles(self, symbol, timeframe, keep_count=1000):
        """
        오래된 캔들 데이터 삭제 (최신 N개만 유지)
        
        Args:
            symbol: 거래쌍 (예: 'BTCUSDT')
            timeframe: 시간봉 (예: '1h', '5m')
            keep_count: 유지할 캔들 개수 (기본값: 1000개)
        
        Returns:
            삭제된 캔들 개수
        """
        # 먼저 현재 개수 확인
        current_count = self.get_data_count(symbol, timeframe)
        
        if current_count <= keep_count:
            return 0  # 삭제할 데이터 없음
        
        # 최신 N개를 제외한 나머지 삭제
        delete_query = """
        DELETE FROM candles 
        WHERE symbol = %s AND timeframe = %s
        AND open_time < (
            SELECT open_time FROM (
                SELECT open_time 
                FROM candles 
                WHERE symbol = %s AND timeframe = %s
                ORDER BY open_time DESC 
                LIMIT 1 OFFSET %s
            ) AS temp
        )
        """
        
        self.cursor.execute(delete_query, (symbol, timeframe, symbol, timeframe, keep_count - 1))
        self.connection.commit()
        deleted = self.cursor.rowcount
        
        if deleted > 0:
            print(f"🗑️ {symbol} ({timeframe}): {deleted}개 오래된 캔들 삭제 (유지: {keep_count}개)")
        
        return deleted
    
    def cleanup_all_old_data(self, keep_count=10000):
        """
        모든 심볼/시간봉의 오래된 데이터 정리
        
        Args:
            keep_count: 각 심볼/시간봉당 유지할 캔들 개수
        
        Returns:
            총 삭제된 캔들 개수
        """
        # 모든 심볼/시간봉 조합 조회
        query = "SELECT DISTINCT symbol, timeframe FROM candles"
        self.cursor.execute(query)
        combinations = self.cursor.fetchall()
        
        total_deleted = 0
        for symbol, timeframe in combinations:
            deleted = self.delete_old_candles(symbol, timeframe, keep_count)
            total_deleted += deleted
        
        return total_deleted
        
        if total_deleted > 0:
            print(f"✅ 총 {total_deleted}개 오래된 캔들 삭제 완료")
        
        return total_deleted
    
    def close(self):
        """
        데이터베이스 연결 종료
        """
        self.cursor.close()
        self.connection.close()
        print("✅ 데이터베이스 연결이 종료되었습니다.")
