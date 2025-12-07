import sys,os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../')

from binance.client import Client
from binance.exceptions import BinanceAPIException
from core.database import CandleDatabase
import requests
import time
import logging
import json
from datetime import timedelta
import pickle


class ChartDownloader:
    """
    바이낸스에서 캔들 데이터를 다운로드하고 MySQL DB에 저장하는 클래스
    """
    
    def __init__(self, db_config=None):
        """
        Args:
            db_config: DB 연결 정보 딕셔너리 (없으면 기본값 사용) 예: {'host': 'localhost', 'user': 'root', 'password': '1234', 'database': 'coin_alarm'}
        """
        self.client = Client()
        
        # DB 설정이 주어지면 사용, 아니면 기본값 사용
        if db_config:
            self.db = CandleDatabase(**db_config)
        else:
            self.db = CandleDatabase()
        
        # 로거 설정
        self.logger = self._setup_logger()
    
    def _setup_logger(self):
        """로거 설정"""
        logger = logging.getLogger('ChartDownloader')
        
        # 기존 핸들러가 없을 때만 설정
        if not logger.handlers:
            # config.json 로드
            try:
                config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                log_level = config.get('logging', {}).get('level', 'INFO')
                log_format = config.get('logging', {}).get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            except:
                log_level = 'INFO'
                log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            
            logger.setLevel(getattr(logging, log_level))
            console_handler = logging.StreamHandler()
            console_handler.setLevel(getattr(logging, log_level))
            formatter = logging.Formatter(log_format)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        return logger
    
    def download_and_save(self, symbol, timeframe, initial_limit=350):
        """
        캔들 데이터를 다운로드하고 DB에 저장
        DB를 체크해서 필요한 만큼만 다운로드
        
        Args:
            symbol: 거래쌍 (예: 'BTCUSDT')
            timeframe: 시간봉 (예: '1h', '5m', '1d')
            initial_limit: 처음 다운로드할 때 가져올 캔들 개수 (기본값: 350)
        
        Returns:
            저장된 캔들 개수
        """
        try:
            self.logger.debug(f"{symbol} ({timeframe}) 데이터 처리 시작")
            
            # API 요청 전 딜레이 (요청 제한 방지)
            time.sleep(0.05)
            
            # 1. DB에 해당 심볼의 데이터가 있는지 확인
            if self.db.check_symbol_exists(symbol, timeframe):
                # 데이터가 있으면 업데이트만 수행
                existing_count = self.db.get_data_count(symbol, timeframe)
                self.logger.debug(f"{symbol}: DB에 기존 데이터 {existing_count}개 발견")
                return self._update_latest_data(symbol, timeframe)
            else:
                # 데이터가 없으면 처음부터 다운로드
                self.logger.info(f"{symbol}: 신규 다운로드 ({initial_limit}개 캔들)")
                klines = self.client.futures_klines(symbol=symbol, interval=timeframe, limit=initial_limit)
                
                if not klines:
                    self.logger.warning(f"{symbol}: 바이낸스에서 데이터를 가져올 수 없습니다")
                    return 0
                
                return self.db.save_candles(symbol, timeframe, klines)
                
        except BinanceAPIException as e:
            self.logger.error(f"{symbol} ({timeframe}) API 에러: {type(e).__name__}(code={e.code}): {e.message}")
            
            # API 제한 에러 처리 (code=-1003)
            if e.code == -1003:
                self.logger.critical(f"API 요청 제한 초과! IP 차단됨")
                # ban 시간 파싱 (밀리초 → 초)
                if 'banned until' in e.message:
                    import re
                    match = re.search(r'banned until (\d+)', e.message)
                    if match:
                        ban_until_ms = int(match.group(1))
                        ban_until_sec = ban_until_ms / 1000
                        now_sec = time.time()
                        wait_time = max(0, ban_until_sec - now_sec)
                        self.logger.critical(f"대기 시간: {wait_time:.0f}초 ({wait_time/60:.1f}분)")
            return 0
            
        except Exception as e:
            self.logger.error(f"{symbol} ({timeframe}) 다운로드 실패: {e}")
            # 흔한 에러 케이스 안내
            if 'Invalid symbol' in str(e):
                self.logger.warning(f"{symbol}은(는) 존재하지 않거나 상장 폐지된 심볼")
            elif 'Invalid interval' in str(e):
                self.logger.warning(f"{timeframe}은(는) 유효하지 않은 시간봉")
            return 0
    
    def _update_latest_data(self, symbol, timeframe):
        """
        DB에 있는 데이터를 최신으로 업데이트
        가장 최근 DB 데이터 이후의 새로운 캔들만 다운로드
        
        Args:
            symbol: 거래쌍
            timeframe: 시간봉
        
        Returns:
            저장된 캔들 개수
        """
        try:
            # API 요청 전 딜레이
            time.sleep(0.5)
            
            # DB에서 가장 최신 캔들 시간 조회 (UTC로 저장되어 있음)
            latest_time = self.db.get_latest_candle_time(symbol, timeframe)
            
            if not latest_time:
                self.logger.warning(f"{symbol} ({timeframe}): DB에 데이터가 없습니다")
                return 0
            
            # DB의 UTC 시간을 UTC 타임스탬프로 변환
            # replace(tzinfo=None)으로 naive datetime을 만든 후 UTC로 해석
            from datetime import timezone
            if latest_time.tzinfo is None:
                # naive datetime을 UTC로 해석
                latest_timestamp = int(latest_time.replace(tzinfo=timezone.utc).timestamp() * 1000)
            else:
                latest_timestamp = int(latest_time.timestamp() * 1000)
            
            self.logger.debug(f"{symbol} DB 최신: KST={latest_time + timedelta(hours=9)}, UTC={latest_time}")
            
            # 최신 시간 이후의 데이터만 다운로드
            # startTime을 설정하면 그 이후의 데이터를 가져옴
            klines = self.client.futures_klines(
                symbol=symbol,
                interval=timeframe,
                startTime=latest_timestamp,
                limit=500  # 최대 500개 
            )
            
            if not klines:
                self.logger.debug(f"{symbol}: 새로운 데이터 없음 (최신 상태)")
                return 0
            
            self.logger.debug(f"{symbol}: {len(klines)}개 새 캔들 다운로드")
            return self.db.save_candles(symbol, timeframe, klines)
            
        except BinanceAPIException as e:
            self.logger.error(f"{symbol} ({timeframe}) 업데이트 실패: {type(e).__name__}(code={e.code}): {e.message}")
            
            # API 제한 에러 처리
            if e.code == -1003:
                self.logger.critical(f"API 요청 제한 초과! 스캔 간격 증가 권장")
            return 0
            
        except Exception as e:
            self.logger.error(f"{symbol} ({timeframe}) 업데이트 실패: {e}")
            return 0
    
    def get_candles_from_db(self, symbol, timeframe, limit=100):
        """
        DB에서 캔들 데이터 조회
        
        Args:
            symbol: 거래쌍 (예: 'BTCUSDT')
            timeframe: 시간봉 (예: '1h', '5m')
            limit: 조회할 캔들 개수 (기본값: 100)
        
        Returns:
            캔들 데이터 리스트
        """
        return self.db.get_candles(symbol, timeframe, limit)

    def update_and_get_candles(self, symbol, timeframe, limit=100):
        """
        DB에서 최신 캔들 데이터 조회

        Args:
            symbol: 거래쌍 (예: 'BTCUSDT')
            timeframe: 시간봉 (예: '1h', '5m')
            limit: 조회할 캔들 개수 (기본값: 100)

        Returns:
            캔들 데이터 리스트
        """
        
        self.download_and_save(symbol, timeframe, initial_limit=1000)
            
        return self.db.get_candles(symbol, timeframe, limit)
    
    def get_all_usdt_symbols(self, limit=None):
        """
        바이낸스 선물에서 거래 가능한 모든 USDT 마진 심볼 리스트 조회
        
        Returns:
            USDT 심볼 리스트 (예: ['BTCUSDT', 'ETHUSDT', ...])
        """
        try:
            # API 요청 전 딜레이
            time.sleep(0.5)
            
            # 선물 거래소 정보 조회
            exchange_info = self.client.futures_exchange_info()
            
            # USDT 마진 심볼만 필터링
            usdt_symbols = []
            for symbol_info in exchange_info['symbols']:
                symbol = symbol_info['symbol']
                status = symbol_info['status']
                
                # USDT로 끝나고 거래 중인(TRADING) 심볼만
                if symbol.endswith('USDT') and status == 'TRADING':
                    usdt_symbols.append(symbol)
            
            print(f"✅ 총 {len(usdt_symbols)}개의 USDT 선물 심볼 발견")
            
            if not limit is None:
                return sorted(usdt_symbols)[:limit]
            
            return sorted(usdt_symbols)
            
        except BinanceAPIException as e:
            print(f"❌ 심볼 리스트 조회 실패: {type(e).__name__}(code={e.code}): {e.message}")
            return []
        except Exception as e:
            print(f"❌ 심볼 리스트 조회 실패: {e}")
            return []
        
    # --- 1. 바이낸스 BASE 자산 목록 가져오기 ---
    def _get_binance_base_assets(self):
        url = "https://api.binance.com/api/v3/exchangeInfo"
        data = requests.get(url).json()
        
        usdt_data = []
        for idx, symbol_info in enumerate(data['symbols']):
            symbol = symbol_info['symbol']
            status = symbol_info['status']
            
            # USDT로 끝나고 거래 중인(TRADING) 심볼만
            if symbol.endswith('USDT') and status == 'TRADING':
                usdt_data.append(data[idx])

        base_assets = set(item["baseAsset"].upper() for item in data["symbols"])
        return base_assets        
    
    def _get_binance_symbol_dict(self):
        url = "https://api.binance.com/api/v3/exchangeInfo"
        data = requests.get(url).json()
        
        usdt_data = []
        for symbol_info in data['symbols']:
            symbol = symbol_info['symbol']
            status = symbol_info['status']
            
            # USDT로 끝나고 거래 중인(TRADING) 심볼만
            if symbol.endswith('USDT') and status == 'TRADING':
                usdt_data.append(symbol_info)
                
        return usdt_data            
        
    def build_binance_coingecko_map(self, cache_file='data/binance_coingecko_map.pkl', use_cache=True):
        """
        바이낸스 심볼 → CoinGecko ID 매핑 생성 및 캐시
        
        Args:
            cache_file: 캐시 파일 경로
            use_cache: 캐시 사용 여부
        
        Returns:
            {바이낸스심볼: coingecko_id} 딕셔너리
        """
        # 캐시 로드 시도
        if use_cache and os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    mapping = pickle.load(f)
                print(f"✅ 캐시에서 매핑 로드 완료: {len(mapping)}개 심볼")
                return mapping
            except Exception as e:
                print(f"⚠️ 캐시 로드 실패: {e}")
        
        # API로 새로 생성
        print("📥 바이낸스 & CoinGecko API로 매핑 생성 중...")
        binance_symbols = self._get_binance_symbol_dict()

        url = "https://api.coingecko.com/api/v3/coins/list?include_platform=false"
        cg_list = requests.get(url).json()

        mapping = {}
        
        symbol_list = [symbol_info["symbol"] for symbol_info in binance_symbols]
        
        for c in cg_list:
            #USDT로 심볼 변환
            usdt_symbol = c["symbol"].upper() + "USDT"
            if usdt_symbol in symbol_list:
                # symbol → id 매핑
                mapping[usdt_symbol] = c["id"]

        # 캐시 저장
        try:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, 'wb') as f:
                pickle.dump(mapping, f)
            print(f"✅ 매핑 캐시 저장 완료: {len(mapping)}개 심볼 → {cache_file}")
        except Exception as e:
            print(f"⚠️ 캐시 저장 실패: {e}")
        
        return mapping    
    
    def get_market_cap(self, symbol):
        mapping = self.build_binance_coingecko_map()
        symbol_up = symbol.upper()

        if symbol_up not in mapping:
            print(f"⚠️ {symbol} 은 CoinGecko 매핑에 없습니다.")
            return None

        coin_id = mapping[symbol_up]

        try:
            url = (
                f"https://api.coingecko.com/api/v3/coins/{coin_id}"
                "?localization=false"
                "&tickers=false"
                "&market_data=true"
                "&community_data=false"
                "&developer_data=false"
                "&sparkline=false"
            )
            data = requests.get(url).json()
            symbol_market_cap = data.get("market_data", {}).get("market_cap", {}).get("usd", None)
            
            if symbol_market_cap is not None:
                return symbol_market_cap / 1_000_000_000  # Convert to billions
            return None
        except Exception as e:
            print(f"⚠️ {symbol} 시가총액 조회 실패: {e}")
            return None

    def download_historical_data(self, symbol, timeframe, start_time, end_time, timezone='KST'):
        """
        특정 시간대의 캔들 데이터를 다운로드하고 DB에 저장
        
        Args:
            symbol: 거래쌍 (예: 'BTCUSDT')
            timeframe: 시간봉 (예: '1h', '5m', '1d')
            start_time: 시작 시간 (datetime 객체 또는 'YYYY-MM-DD HH:MM:SS' 문자열)
            end_time: 종료 시간 (datetime 객체 또는 'YYYY-MM-DD HH:MM:SS' 문자열)
            timezone: 'KST' (한국시간, 기본값) 또는 'UTC' (세계시)
        
        Returns:
            저장된 캔들 개수
        """
        from datetime import datetime, timedelta
        import pytz
        
        # 문자열을 datetime으로 변환
        if isinstance(start_time, str):
            start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        if isinstance(end_time, str):
            end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
        
        # 타임존 객체 생성
        kst = pytz.timezone('Asia/Seoul')
        utc = pytz.UTC
        
        # KST → UTC 변환 (바이낸스 API는 UTC 기준)
        if timezone.upper() == 'KST':
            print(f"\n📥 {symbol} ({timeframe}) 히스토리 데이터 다운로드 (KST → UTC 변환)")
            print(f" 입력 시간 (KST): {start_time} ~ {end_time}")
            
            # naive datetime을 KST로 지정
            if start_time.tzinfo is None:
                start_time = kst.localize(start_time)
            if end_time.tzinfo is None:
                end_time = kst.localize(end_time)
            
            # UTC로 변환
            start_time_utc = start_time.astimezone(utc)
            end_time_utc = end_time.astimezone(utc)
            
            print(f" 변환 시간 (UTC): {start_time_utc} ~ {end_time_utc}")
        else:
            print(f"\n📥 {symbol} ({timeframe}) 히스토리 데이터 다운로드")
            print(f" 기간 (UTC): {start_time} ~ {end_time}")
            
            # UTC로 지정
            if start_time.tzinfo is None:
                start_time_utc = utc.localize(start_time)
            else:
                start_time_utc = start_time
            if end_time.tzinfo is None:
                end_time_utc = utc.localize(end_time)
            else:
                end_time_utc = end_time
        
        # datetime을 밀리초 타임스탬프로 변환 (UTC 기준)
        start_timestamp = int(start_time_utc.timestamp() * 1000)
        end_timestamp = int(end_time_utc.timestamp() * 1000)
        
        try:
            # API 요청 전 딜레이
            time.sleep(0.5)
            
            # 바이낸스 API는 최대 1500개씩만 가져올 수 있음
            all_klines = []
            current_start = start_timestamp
            
            while current_start < end_timestamp:
                klines = self.client.futures_klines(
                    symbol=symbol,
                    interval=timeframe,
                    startTime=current_start,
                    endTime=end_timestamp,
                    limit=1500
                )
                
                if not klines:
                    break
                
                all_klines.extend(klines)
                
                # 다음 요청의 시작 시간을 마지막 캔들의 종료 시간 + 1ms로 설정
                current_start = klines[-1][6] + 1  # klines[-1][6]은 종료 시간
                
                print(f"  ✓ {len(klines)}개 캔들 다운로드 완료 (전체: {len(all_klines)}개)")
                
                # API 제한 방지를 위한 딜레이
                time.sleep(0.5)
            
            print(f"\n✅ 총 {len(all_klines)}개 캔들 다운로드 완료")
            
            if all_klines:
                saved_count = self.db.save_candles(symbol, timeframe, all_klines)
                print(f"✅ {symbol} ({timeframe}): {saved_count}개 캔들 저장 완료")
                return saved_count
            else:
                print(f"⚠️ {symbol} ({timeframe}): 다운로드할 데이터가 없습니다.")
                return 0
                
        except BinanceAPIException as e:
            print(f"❌ {symbol} ({timeframe}) 다운로드 실패: {type(e).__name__}(code={e.code}): {e.message}")
            return 0
        except Exception as e:
            print(f"❌ {symbol} ({timeframe}) 다운로드 실패: {e}")
            return 0
    
    def get_candles_by_time_range(self, symbol, timeframe, start_time, end_time, auto_update=True, timezone='KST'):
        """
        특정 시간대의 캔들 데이터를 DB에서 조회
        데이터가 부족하거나 없으면 auto_update 옵션에 따라 다운로드
        
        Args:
            symbol: 거래쌍 (예: 'BTCUSDT')
            timeframe: 시간봉 (예: '1h', '5m', '1d')
            start_time: 시작 시간 (datetime 객체 또는 'YYYY-MM-DD HH:MM:SS' 문자열)
            end_time: 종료 시간 (datetime 객체 또는 'YYYY-MM-DD HH:MM:SS' 문자열)
            auto_update: True면 데이터 부족 시 자동 다운로드, False면 print만
            timezone: 'KST' (한국시간, 기본값) 또는 'UTC' (세계시)
        
        Returns:
            캔들 데이터 리스트 [(open_time, open, high, low, close, volume, quote_volume), ...]
        """
        from datetime import datetime, timedelta
        
        # 문자열을 datetime으로 변환
        if isinstance(start_time, str):
            start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        if isinstance(end_time, str):
            end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
        
        # 원본 시간 저장 (출력용)
        original_start = start_time
        original_end = end_time
        
        # KST → UTC 변환 (DB는 UTC로 저장되어 있음)
        if timezone.upper() == 'KST':
            print(f"\n🔍 {symbol} ({timeframe}) 데이터 조회 (KST → UTC 변환)")
            print(f"   입력 시간 (KST): {original_start} ~ {original_end}")
            start_time = start_time - timedelta(hours=9)
            end_time = end_time - timedelta(hours=9)
            print(f"   변환 시간 (UTC): {start_time} ~ {end_time}")
        else:
            print(f"\n🔍 {symbol} ({timeframe}) 데이터 조회")
            print(f"   기간 (UTC): {start_time} ~ {end_time}")
        
        # DB에서 해당 시간대 데이터 조회
        query = """
        SELECT open_time, open_price, high_price, low_price, close_price, volume, quote_volume
        FROM candles 
        WHERE symbol = %s AND timeframe = %s 
        AND open_time >= %s AND open_time <= %s
        ORDER BY open_time ASC
        """
        
        self.db.cursor.execute(query, (symbol, timeframe, start_time, end_time))
        results = self.db.cursor.fetchall()
        
        if results:
            print(f"✅ DB에서 {len(results)}개 캔들 조회 완료")
            return results
        else:
            print(f"⚠️ DB에 해당 시간대의 데이터가 없습니다.")
            
            if auto_update:
                print(f"🔄 자동 다운로드를 시작합니다...")
                self.download_historical_data(symbol, timeframe, start_time, end_time, timezone='UTC')
                
                # 다시 조회
                self.db.cursor.execute(query, (symbol, timeframe, start_time, end_time))
                results = self.db.cursor.fetchall()
                
                if results:
                    print(f"✅ 다운로드 후 {len(results)}개 캔들 조회 완료")
                    return results
                else:
                    print(f"❌ 다운로드 후에도 데이터를 찾을 수 없습니다.")
                    return []
            else:
                print(f"💡 auto_update=True로 설정하면 자동으로 다운로드합니다.")
                return []

    def close(self):
        """
        DB 연결 종료
        """
        self.db.close()
        
        
if __name__ == "__main__":
    # 테스트용 실행 코드
    downloader = ChartDownloader()
    
    # 한국시간으로 다운로드 (기본값)
    downloader.download_historical_data('GRIFFAINUSDT', '1m', '2025-11-29 11:30:00', '2025-11-29 12:00:00', timezone='KST')

    # 한국시간으로 조회
    candles = downloader.get_candles_by_time_range('GRIFFAINUSDT', '1m', '2025-11-29 11:30:00', '2025-11-29 12:00:00', timezone='KST')
    print(f"\n조회된 캔들: {len(candles)}개")