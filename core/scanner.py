"""
거래량 급증 스캔 로직

모든 USDT 심볼의 데이터를 최신화하고 거래량 급증을 확인
"""
import sys,os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import os
import logging
from datetime import datetime, timedelta
from pytz import timezone
from core.downloader import ChartDownloader
from service.filter import Filter
from core.scheduler_state import scheduler_info


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
        
        # 로거 설정
        self.logger = self._setup_logger()
    
    def _load_config(self):
        """설정 파일 로드"""
        try:
            if not os.path.exists(self.config_file):
                self.logger.critical(f"❌ 설정 파일({self.config_file})이 없습니다.")
                self.logger.critical("설정 파일을 작성하시오!!. 프로그램이 종료됩니다.")
                exit()
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 필수 키 검증
            required_keys = {
                'scanner': ['symbol_limit', 'batch_size', 'batch_delay', 'keep_candles'],
                'tot_timeframes': None,  # 리스트 타입
                'filter': None  # 리스트 타입, 하위 검증 필요
            }
            
            # 최상위 키 검증
            for key in required_keys.keys():
                if key not in config:
                    self.logger.critical(f"❌ 설정 파일에 필수 키 '{key}'가 없습니다.")
                    self.logger.critical("설정 파일을 확인하시오!!. 프로그램이 종료됩니다.")
                    exit()
            
            # scanner 하위 키 검증
            for sub_key in required_keys['scanner']:
                if sub_key not in config['scanner']:
                    self.logger.critical(f"❌ 설정 파일의 'scanner'에 필수 키 '{sub_key}'가 없습니다.")
                    self.logger.critical("설정 파일을 확인하시오!!. 프로그램이 종료됩니다.")
                    exit()
            
            # filter 배열 검증
            if not isinstance(config['filter'], list) or len(config['filter']) == 0:
                self.logger.critical(f"❌ 설정 파일의 'filter'는 비어있지 않은 배열이어야 합니다.")
                self.logger.critical("설정 파일을 확인하시오!!. 프로그램이 종료됩니다.")
                exit()
            
            # 각 필터 설정 검증
            filter_required_keys = ['types', 'using_timeframe', 'interval', 'period', 'window']
            for i, filter_config in enumerate(config['filter']):
                for key in filter_required_keys:
                    if key not in filter_config:
                        self.logger.critical(f"❌ 설정 파일의 filter[{i}]에 필수 키 '{key}'가 없습니다.")
                        self.logger.critical("설정 파일을 확인하시오!!. 프로그램이 종료됩니다.")
                        exit()
            
            return config

        except json.JSONDecodeError as e:
            self.logger.critical(f"❌ 설정 파일 JSON 형식 오류: {e}")
            self.logger.critical("설정 파일을 확인하시오!!. 프로그램이 종료됩니다.")
            exit()
        except Exception as e:
            self.logger.critical(f"❌ 설정 파일 로드 실패: {e}")
            self.logger.critical("설정 파일을 확인하시오!!. 프로그램이 종료됩니다.")
            exit()
            
    def _setup_logger(self):
        """로거 설정"""
        logger = logging.getLogger('SurgeScanner')
        
        # 기존 핸들러 제거 (중복 방지)
        if logger.handlers:
            logger.handlers.clear()
        
        # 로그 레벨 설정
        log_level = self.config.get('logging', {}).get('level', 'INFO')
        logger.setLevel(getattr(logging, log_level))
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level))
        
        # 포맷 설정
        log_format = self.config.get('logging', {}).get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        formatter = logging.Formatter(log_format)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        return logger
    
    def _get_current_time(self):
        return datetime.now()
    
    def scan(self):
        """
        전체 스캔 실행
        1. 데이터 최신화
        2. 거래량 급증 필터링
        3. 오래된 데이터 정리
        4. 결과 저장
        """
        self.logger.info("="*50)
        self.logger.info(f"거래량 급증 스캔 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("="*50)
        
        # 다운로더와 필터 생성
        downloader = ChartDownloader(self.db_config)
        filter_obj = Filter()  # DB 의존성 제거
        
        # 설정에서 limit 값 가져오기
        symbol_limit = self.config.get('scanner').get('symbol_limit')
        
        # 모든 USDT 심볼 가져오기
        all_symbols = downloader.get_all_usdt_symbols(limit=symbol_limit)
        self.logger.info(f"총 {len(all_symbols)}개 심볼 확인 중 (설정: {symbol_limit if symbol_limit else '전체'})")
        
        # 확인할 시간봉들 (설정에서 가져오기)
        timeframes = self.config.get('tot_timeframes')
        
        # 1단계: 데이터 최신화
        self._update_data(downloader, all_symbols, timeframes)
        
        # 2단계: 거래량 급증 필터링
        surge_data = self.apply_filter(filter_obj, all_symbols)
        
        # 3단계: 오래된 데이터 정리
        self._cleanup_old_data(downloader)
        
        # 결과 저장
        self._save_results(surge_data)
        
        # 연결 종료
        downloader.close()
        
        self.logger.info(f"스캔 완료! 결과가 {self.result_file}에 저장되었습니다")
    
    def _update_data(self, downloader:ChartDownloader, symbols, timeframes):
        """
        모든 심볼의 데이터 최신화
        배치 처리로 API 제한 방지
        """
        self.logger.info("데이터 최신화 시작")
        update_count = 0
        batch_size = self.config.get('scanner', {}).get('batch_size', 10)
        batch_delay = self.config.get('scanner', {}).get('batch_delay', 1)
        
        for timeframe in timeframes:
            self.logger.info(f"{timeframe} 시간봉 업데이트 시작")
            
            # 심볼을 배치로 나누기
            total_batches = (len(symbols) - 1) // batch_size + 1
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i+batch_size]
                batch_num = i // batch_size + 1
                
                self.logger.info(f"{timeframe} 배치 {batch_num}/{total_batches} 처리 중 ({len(batch)}개 심볼)")
                
                for symbol in batch:
                    try:
                        downloader.download_and_save(symbol, timeframe, initial_limit=350)
                        update_count += 1
                        
                    except Exception as e:
                        self.logger.error(f"{symbol} 업데이트 실패: {e}")
                
                # 배치 간 딜레이 (API 제한 방지)
                import time
                time.sleep(batch_delay)
        
        self.logger.info(f"데이터 업데이트 완료 (총 {update_count}개)")

    def _check_filter_scheduling(self, filter_configs):
        """
        필터 스케줄링 확인 및 트리거 설정
        
        Args:
            filter_configs: 필터 설정 리스트
        """
        current_time = self._get_current_time()
        
        for filter_config in filter_configs:
            filter_type = filter_config.get('types')
            interval = filter_config.get('interval')
            filter_enable = filter_config.get('enable')
            
            if filter_type is None or interval is None:
                self.logger.warning(f"⚠️ 필터 설정 오류: 'types' 또는 'interval' 누락")
                continue
            
            if filter_enable is False:
                self.logger.info(f"⏸️ 필터 '{filter_type}' 비활성화됨, 스케줄링 건너뜀")
                continue
            
            # interval 파싱
            try:
                if interval.endswith('m'):
                    minutes = int(interval.replace('m', ''))
                elif interval.endswith('h'):
                    minutes = int(interval.replace('h', '')) * 60
                elif interval.endswith('d'):
                    minutes = int(interval.replace('d', '')) * 1440
                else:
                    self.logger.warning(f"⚠️ 필터 '{filter_type}': interval 형식 오류 ('{interval}'). 'm', 'h', 'd' 단위를 사용하세요.")
                    continue
            except ValueError:
                self.logger.warning(f"⚠️ 필터 '{filter_type}': interval 값 변환 실패 ('{interval}')")
                continue
            
            # scheduler_info에 필터 타입이 없으면 초기화
            if filter_type not in scheduler_info:
                scheduler_info[filter_type] = {
                    'start_time': None,
                    'elapsed_time': timedelta(0),
                    'trigger': False
                }
                self.logger.info(f"🆕 필터 '{filter_type}' 스케줄러 초기화")
            
            # start_time이 None이면 최초 실행
            if scheduler_info[filter_type]['start_time'] is None:
                scheduler_info[filter_type]['start_time'] = current_time
                scheduler_info[filter_type]['trigger'] = True
                self.logger.info(f"✅ 필터 '{filter_type}' 최초 실행 트리거 (interval: {interval})")
            else:
                # 경과 시간 계산
                elapsed_time = current_time - scheduler_info[filter_type]['start_time']
                scheduler_info[filter_type]['elapsed_time'] = elapsed_time
                
                # interval 이상 경과했으면 트리거
                if elapsed_time >= timedelta(minutes=minutes):
                    scheduler_info[filter_type]['start_time'] = current_time
                    scheduler_info[filter_type]['trigger'] = True
                    self.logger.info(f"✅ 필터 '{filter_type}' 트리거 (경과: {int(elapsed_time.total_seconds()/60)}분, interval: {interval})")
                else:
                    scheduler_info[filter_type]['trigger'] = False
                    remaining = timedelta(minutes=minutes) - elapsed_time
                    self.logger.info(f"⏭️  필터 '{filter_type}' 대기 중 (남은 시간: {int(remaining.total_seconds()/60)}분/{interval})")
    def apply_filter(self, filter_obj:Filter, symbols):
        """
        거래량 급증 필터링
        """
        surge_data = []
        
        # 설정에서 필터 배열 가져오기
        filter_configs = self.config.get('filter', [])
        
        # 하위 호환성: filter가 dict면 리스트로 변환
        if isinstance(filter_configs, dict):
            filter_configs = [filter_configs]
        
        # 필터 이름들 출력
        filter_names = [f.get('types', 'unknown') for f in filter_configs]
        self.logger.info(f"🔍 사용 중인 필터: {', '.join(filter_names)}")
        
        downloader = ChartDownloader(self.db_config)
            
        surge_symbols = []
        
        # 필터 스케줄링 확인
        self._check_filter_scheduling(filter_configs)
        
        # 트리거된 필터들 확인
        triggered_filters = {}
        for filter_config in filter_configs:
            filter_type = filter_config.get('types')
            if filter_type in scheduler_info:
                if scheduler_info[filter_type].get('trigger', False):
                    triggered_filters[filter_type] = filter_config
        
        if not triggered_filters:
            self.logger.info("트리거된 필터가 없습니다. 모든 필터가 대기 중입니다.")
            downloader.close()
            return surge_data
        
        self.logger.info(f"트리거된 필터: {', '.join(triggered_filters.keys())}")
        
        # 각 심볼별로 데이터를 가져와서 필터에 주입
        for symbol in symbols:
            try:
                # 트리거된 필터들만 실행
                for filter_type, filter_config in triggered_filters.items():
                    
                    if filter_type == '3step_surge':
                        # 해당 필터 설정 값들 가져오기
                        filter_timeframes:list = filter_config.get('using_timeframe')
                        volume_range_multiplier = filter_config.get('volume_range_multiplier')
                        period = filter_config.get('period')
                        window = filter_config.get('window')
                        range_multiplier = filter_config.get('range_multiplier')
                        strong_candle_count = filter_config.get('strong_candle_count', 0)
                        upper_wick_ratio = filter_config.get('upper_wick_ratio', 0.2)
                        lower_wick_ratio = filter_config.get('lower_wick_ratio', 0.1)

                        for timeframe in filter_timeframes:
                            candles = downloader.db.get_candles(symbol, timeframe, limit=window + period + 1)
                            pattern_time = filter_obj._three_step_surge_filter(
                                candles, symbol, volume_range_multiplier, period, window, range_multiplier,
                                strong_candle_count=strong_candle_count,
                                upper_wick_ratio=upper_wick_ratio,
                                lower_wick_ratio=lower_wick_ratio
                            )
                            if pattern_time:
                                surge_symbols.append({
                                    "symbol": symbol, 
                                    "time": pattern_time, 
                                    "filter": filter_type,
                                    "timeframe": timeframe
                                })
                                break  # 하나의 필터에 걸리면 다음 심볼로
                    
                    elif filter_type == 'high_volume_spike':
                        # 해당 필터 설정 값들 가져오기
                        filter_timeframes:list = filter_config.get('using_timeframe')
                        period = filter_config.get('period')
                        window = filter_config.get('window')
                        volume_range_multiplier = filter_config.get('volume_range_multiplier')
                        spike_threshold = filter_config.get('spike_threshold')
                        
                        for timeframe in filter_timeframes:
                            candles = downloader.db.get_candles(symbol, timeframe, limit=window + period + 1)
                            pattern_time = filter_obj._high_volume_spike_filter(candles, symbol, downloader=downloader, timeframe=timeframe, period=period, window=window, volume_range_multiplier=volume_range_multiplier, spike_threshold=spike_threshold)
                            if pattern_time:
                                surge_symbols.append({
                                    "symbol": symbol, 
                                    "time": pattern_time, 
                                    "filter": filter_type,
                                    "timeframe": timeframe
                                })
                                break  # 하나의 필터에 걸리면 다음 심볼로
            
            except Exception as e:
                self.logger.warning(f"⚠️ {symbol} 확인 중 오류: {e}")
        
        # 필터 실행 완료 후 trigger를 False로 설정
        for filter_type in triggered_filters.keys():
            scheduler_info[filter_type]['trigger'] = False
            self.logger.debug(f"필터 '{filter_type}' 실행 완료, trigger=False 설정")
        
        if surge_symbols:
            self.logger.info(f"🔥 총 {len(surge_symbols)}개 심볼 발견")
            
            # 시가총액 정보 추가
            self.logger.info(f"💰 시가총액 정보 가져오는 중...")
            for symbol_info in surge_symbols:
                try:
                    market_cap = downloader.get_market_cap(symbol_info['symbol'])
                    symbol_info['market_cap'] = market_cap
                except Exception as e:
                    self.logger.warning(f"⚠️ {symbol_info['symbol']} 시가총액 조회 실패: {e}")
                    symbol_info['market_cap'] = None
            
            # timeframe별로 그룹화
            timeframe_groups = {}
            for symbol_info in surge_symbols:
                tf = symbol_info['timeframe']
                if tf not in timeframe_groups:
                    timeframe_groups[tf] = []
                timeframe_groups[tf].append(symbol_info)
            
            # surge_data 생성
            for tf, symbols_list in timeframe_groups.items():
                surge_data.append({
                    "timeframe": tf,
                    "count": len(symbols_list),
                    "symbols": symbols_list
                })
                self.logger.info(f"🔥 {tf}: {len(symbols_list)}개 발견")
        
        downloader.close()
        return surge_data
    
    def _cleanup_old_data(self, downloader: ChartDownloader):
        """
        오래된 데이터 정리
        각 심볼/시간봉당 최신 N개만 유지
        """
        self.logger.info(f"\n🗑️ 오래된 데이터 정리 중...")
        keep_count = self.config.get('scanner', {}).get('keep_candles', 10000)
        deleted = downloader.db.cleanup_all_old_data(keep_count=keep_count)
        if deleted > 0:
            self.logger.info(f"✅ {deleted}개 오래된 캔들 삭제 완료")
        else:
            self.logger.info(f"✅ 정리할 데이터 없음")
    
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
                try:
                    with open(self.history_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            history = json.loads(content)
                        else:
                            history = {"scans": []}
                except (json.JSONDecodeError, ValueError):
                    self.logger.warning("이력 파일이 손상되었습니다. 새로 생성합니다.")
                    history = {"scans": []}
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
            
            self.logger.info(f"📝 스캔 이력 저장 완료 (총 {len(history['scans'])}개)")
            
        except Exception as e:
            self.logger.warning(f"⚠️ 이력 저장 실패: {e}")
    
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
    # DB 설정 (본인 설정에 맞게 수정)
    DB_CONFIG = {
        'host': 'localhost',
        'user': 'root',
        'password': '1234',
        'database': 'coin_chart'
    }

    # 스캐너 생성
    scanner = SurgeScanner(DB_CONFIG, result_file="data/surge_results.json", history_file="data/surge_history.json")
    downloader = ChartDownloader()
    filter_obj = Filter()
    symbols = ['GRIFFAINUSDT']
    timeframe = '1m'
    volume_range_multiplier = 5
    range_multiplier = 3
    period = 14
    window = 30 
    candles = downloader.get_candles_by_time_range('1000LUNCUSDT', '5m', '2025-12-04 0:20:00', '2025-12-05 05:00:00', timezone='KST')
    pattern_time = filter_obj._three_step_surge_filter(candles, '1000LUNCUSDT', volume_range_multiplier, period, window, range_multiplier, start_time='2025-12-04 22:00:00', end_time='2025-12-05 03:00:00', timezone='KST')
    if pattern_time:
        print(f"패턴 발견 시간: {pattern_time}")

