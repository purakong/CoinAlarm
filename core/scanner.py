"""
거래량 급증 스캔 로직

모든 USDT 심볼의 데이터를 최신화하고 거래량 급증을 확인
"""
import sys,os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../')

import json
import os
from datetime import datetime
from core.downloader import ChartDownloader
from service.filter import Filter


class SurgeScanner:
    """거래량 급증 스캐너"""
    
    def __init__(self, db_config, result_file="surge_results.json", history_file="surge_history.json", config_file="config.json"):
        """
        Args:
            db_config: DB 연결 정보
            result_file: 최신 결과 저장 파일명
            history_file: 이력 저장 파일명
            config_file: 설정 파일명
        """
        self.db_config = db_config
        self.result_file = result_file
        self.history_file = history_file
        self.config_file = config_file
        self.config = self._load_config()
        self.latest_results = {
            "last_update": None,
            "surge_coins": []
        }
    
    def _load_config(self):
        """설정 파일 로드"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"⚠️  설정 파일({self.config_file})이 없습니다. 기본값 사용")
                return {
                    "scanner": {
                        "symbol_limit": 200,
                        "batch_size": 10,
                        "batch_delay": 1,
                        "keep_candles": 500
                    },
                    "timeframes": ["1m"],
                    "filter": {
                        "type": "3step_surge",
                        "threshold": 1.1,
                        "period": 14
                    }
                }
        except Exception as e:
            print(f"❌ 설정 파일 로드 실패: {e}. 기본값 사용")
            return {
                "scanner": {
                    "symbol_limit": 200,
                    "batch_size": 10,
                    "batch_delay": 1,
                    "keep_candles": 500
                },
                "timeframes": ["1m"],
                "filter": {
                    "type": "3step_surge",
                    "threshold": 1.1,
                    "period": 14
                }
            }
    
    def scan(self):
        """
        전체 스캔 실행
        1. 데이터 최신화
        2. 거래량 급증 필터링
        3. 오래된 데이터 정리
        4. 결과 저장
        """
        print("\n" + "="*50)
        print(f"🔍 거래량 급증 스캔 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50)
        
        try:
            # 다운로더와 필터 생성
            downloader = ChartDownloader(self.db_config)
            filter_obj = Filter()  # DB 의존성 제거
            
            # 설정에서 limit 값 가져오기
            symbol_limit = self.config.get('scanner', {}).get('symbol_limit', None)
            
            # 모든 USDT 심볼 가져오기
            all_symbols = downloader.get_all_usdt_symbols(limit=symbol_limit)
            print(f"📊 총 {len(all_symbols)}개 심볼 확인 중... (설정: {symbol_limit if symbol_limit else '전체'})")
            # all_symbols = ['GRIFFAINUSDT']
            
            # 확인할 시간봉들 (설정에서 가져오기)
            timeframes = self.config.get('timeframes', ['1m'])
            
            # 1단계: 데이터 최신화
            self._update_data(downloader, all_symbols, timeframes)
            
            # 2단계: 거래량 급증 필터링
            surge_data = self._filter_surge(filter_obj, all_symbols, timeframes)
            
            # 3단계: 오래된 데이터 정리
            self._cleanup_old_data(downloader)
            
            # 결과 저장
            self._save_results(surge_data)
            
            # 연결 종료
            downloader.close()
            
            print(f"\n✅ 스캔 완료! 결과가 {self.result_file}에 저장되었습니다.")
            
        except Exception as e:
            print(f"❌ 스캔 중 오류 발생: {e}")
    
    def _update_data(self, downloader:ChartDownloader, symbols, timeframes):
        """
        모든 심볼의 데이터 최신화
        배치 처리로 API 제한 방지
        """
        print(f"\n📥 데이터 최신화 중...")
        update_count = 0
        batch_size = self.config.get('scanner', {}).get('batch_size', 10)
        
        for timeframe in timeframes:
            print(f"  ⏰ {timeframe} 시간봉 업데이트...")
            
            # 심볼을 배치로 나누기
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i+batch_size]
                
                print(f"    배치 {i//batch_size + 1}/{(len(symbols)-1)//batch_size + 1} 처리 중... ({len(batch)}개 심볼)")
                
                for symbol in batch:
                    try:
                        downloader.download_and_save(symbol, timeframe, initial_limit=100)
                        update_count += 1
                        
                    except Exception as e:
                        # 에러 발생해도 계속 진행
                        pass
                
                # 배치 간 딜레이 (API 제한 방지)
                import time
                batch_delay = self.config.get('scanner', {}).get('batch_delay', 1)
                time.sleep(batch_delay)
        
        print(f"✅ 데이터 업데이트 완료! (총 {update_count}개 업데이트)")

    def _filter_surge(self, filter_obj:Filter, symbols, timeframes):
        """
        거래량 급증 필터링
        """
        surge_data = []
        
        # 설정에서 필터 옵션 가져오기
        filter_config = self.config.get('filter', {})
        filter_type = filter_config.get('type', '3step_surge')
        threshold = filter_config.get('threshold', 1.1)
        period = filter_config.get('period', 14)
        window = filter_config.get('window', 30)
        range_multiplier = filter_config.get('range_multiplier', 3.0)
        
        # DB 접근용 downloader 생성
        downloader = ChartDownloader(self.db_config)
        
        for timeframe in timeframes:
            print(f"\n🔍 {timeframe} 시간봉 필터링 중...")
            
            surge_symbols = []
            
            # 각 심볼별로 데이터를 가져와서 필터에 주입
            for symbol in symbols:
                try:
                    # DB에서 캔들 데이터 가져오기
                    if filter_type == 'surge_volume' or filter_type == 'surge':
                        candles = downloader.db.get_candles(symbol, timeframe, limit=period + 2)
                        result = filter_obj._surge_volume_filter(candles, symbol, threshold, period)
                        if result:
                            surge_symbols.append({"symbol": symbol, "time": None})
                    
                    elif filter_type == '3step_surge':
                        candles = downloader.db.get_candles(symbol, timeframe, limit=window + period)
                        pattern_time = filter_obj._three_step_surge_filter(candles, symbol, threshold, period, window, range_multiplier)
                        if pattern_time:
                            surge_symbols.append({"symbol": symbol, "time": pattern_time})
                
                except Exception as e:
                    print(f"⚠️ {symbol} 확인 중 오류: {e}")
            
            if surge_symbols:
                print(f"🔥 {timeframe}: {len(surge_symbols)}개 발견")
                
                # 시가총액 정보 추가
                print(f"💰 시가총액 정보 가져오는 중...")
                for symbol_info in surge_symbols:
                    try:
                        market_cap = downloader.get_market_cap(symbol_info['symbol'])
                        symbol_info['market_cap'] = market_cap
                    except Exception as e:
                        print(f"⚠️ {symbol_info['symbol']} 시가총액 조회 실패: {e}")
                        symbol_info['market_cap'] = None
                
                surge_data.append({
                    "timeframe": timeframe,
                    "count": len(surge_symbols),
                    "symbols": surge_symbols
                })
        
        downloader.close()
        return surge_data
    
    def _cleanup_old_data(self, downloader: ChartDownloader):
        """
        오래된 데이터 정리
        각 심볼/시간봉당 최신 N개만 유지
        """
        print(f"\n🗑️ 오래된 데이터 정리 중...")
        keep_count = self.config.get('scanner', {}).get('keep_candles', 10000)
        deleted = downloader.db.cleanup_all_old_data(keep_count=keep_count)
        if deleted > 0:
            print(f"✅ {deleted}개 오래된 캔들 삭제 완료")
        else:
            print(f"✅ 정리할 데이터 없음")
    
    def _save_results(self, surge_data):
        """
        결과 저장
        - surge_results.json: 최신 결과 (덮어쓰기)
        - surge_history.json: 전체 이력 (추가)
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 최신 결과
        self.latest_results = {
            "last_update": timestamp,
            "surge_coins": surge_data
        }
        
        # 최신 결과 파일에 저장 (덮어쓰기)
        with open(self.result_file, 'w', encoding='utf-8') as f:
            json.dump(self.latest_results, f, ensure_ascii=False, indent=2)
        
        # 이력 파일에 추가 (surge_coins가 있을 때만)
        try:
            # surge_coins에 실제 발견된 코인이 있는지 확인
            has_surge = False
            for item in surge_data:
                if item.get('symbols') and len(item['symbols']) > 0:
                    has_surge = True
                    break
            
            # 발견된 코인이 없으면 이력에 저장하지 않음
            if not has_surge:
                return
            
            # 기존 이력 로드
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            else:
                history = {"scans": []}
            
            # 새 스캔 결과 추가
            scan_result = {
                "timestamp": timestamp,
                "surge_coins": surge_data
            }
            history["scans"].append(scan_result)
            
            # 이력 저장 (최대 300개만 유지)
            max_history = 300
            if len(history["scans"]) > max_history:
                history["scans"] = history["scans"][-max_history:]
            
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            
            print(f"📝 스캔 이력 저장 완료 (총 {len(history['scans'])}개)")
            
        except Exception as e:
            print(f"⚠️ 이력 저장 실패: {e}")
    
    def get_latest_results(self):
        """
        최신 결과 반환
        """
        try:
            with open(self.result_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return self.latest_results
    
    def get_history(self, limit=10):
        """
        스캔 이력 반환
        
        Args:
            limit: 반환할 최대 개수 (기본값: 10, None이면 전체)
        
        Returns:
            이력 리스트 (최신순)
        """
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
                scans = history.get("scans", [])
                
                # 최신순 정렬 (역순)
                scans.reverse()
                
                if limit:
                    return scans[:limit]
                return scans
        except:
            return []
        
if __name__ == "__main__":
    downloader = ChartDownloader()
    filter_obj = Filter()
    symbols = ['GRIFFAINUSDT']
    timeframe = '1m'
    threshold = 1.1
    period = 14
    window = 30
    candles = downloader.get_candles_by_time_range('GRIFFAINUSDT', '1m', '2025-11-29 11:00:00', '2025-11-29 12:00:00', timezone='KST')
    pattern_time = filter_obj._three_step_surge_filter(candles, 'GRIFFAINUSDT', threshold, period, window, start_time='2025-11-29 11:00:00', end_time='2025-11-29 12:00:00', timezone='KST')
    if pattern_time:
        print(f"패턴 발견 시간: {pattern_time}")
    
                                                 