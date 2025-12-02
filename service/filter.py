"""
거래량 급증 필터

캔들 데이터를 분석해서 조건에 맞는 코인을 찾아내는 필터
데이터는 외부에서 주입받아 순수 분석 로직만 수행
"""


class Filter:
    """
    거래량 급증 필터 (순수 분석 로직)
    
    최근 14개 캔들의 평균 거래량 대비 최신 캔들의 거래량이 
    임계값(기본 2배) 이상인 심볼을 찾습니다.
    
    데이터는 외부에서 주입받아야 하며, DB 의존성이 없습니다.
    """
    
    def __init__(self):
        """
        순수 분석 필터 - DB 의존성 없음
        """
        pass
            
    
    def _surge_volume_filter(self, candles, symbol, threshold=2.0, period=14):
        """
        특정 심볼의 거래량 급증 여부 확인
        
        Args:
            candles: 캔들 데이터 리스트 [(open_time, open, high, low, close, volume, quote_volume), ...]
            symbol: 확인할 심볼 (예: 'BTCUSDT') - 로깅용
            threshold: 임계값 배수 (기본값: 2.0 = 2배)
            period: 평균 계산 기간 (기본값: 14개 캔들)
        
        Returns:
            True: 거래량 급증, False: 정상
        """
        if len(candles) < period + 2:
            # 데이터가 충분하지 않으면 False
            return False
        
        # 최신 캔들 (마지막 - 미완성 가능)
        current_candle = candles[-1]
        current_volume = float(current_candle[5])
        
        # 바로 이전 완성된 캔들 (마지막에서 두 번째)
        previous_completed_candle = candles[-2]
        previous_volume = float(previous_completed_candle[5])
        
        # 평균 계산 1: 현재 캔들 비교용 (현재 1개만 제외, period개 평균)
        avg_candles_for_current = candles[-period-1:-1]  # 현재 제외, period개
        avg_volume_for_current = sum(float(c[5]) for c in avg_candles_for_current) / len(avg_candles_for_current)
        
        # 평균 계산 2: 이전 캔들 비교용 (현재+이전 2개 제외, period개 평균)
        avg_candles_for_previous = candles[-period-2:-2]  # 현재+이전 제외, period개
       
        avg_volume_for_previous = sum(float(c[5]) for c in avg_candles_for_previous) / len(avg_candles_for_previous)
        
        # 현재 캔들 체크 (정확한 평균으로 비교)
        current_surge = current_volume >= avg_volume_for_current * threshold
        
        # 이전 완성 캔들 체크 (정확한 평균으로 비교)
        previous_surge = previous_volume >= avg_volume_for_previous * threshold
        
        if current_surge or previous_surge:
            surge_type = []
            if current_surge:
                surge_type.append(f"현재: {current_volume:.2f} (평균: {avg_volume_for_current:.2f}, {current_volume/avg_volume_for_current:.2f}x)")
            if previous_surge:
                surge_type.append(f"이전: {previous_volume:.2f} (평균: {avg_volume_for_previous:.2f}, {previous_volume/avg_volume_for_previous:.2f}x)")

            print(f"🔥 {symbol}: 거래량 급증! {', '.join(surge_type)}")
            return True
        
        return False
    
    def _three_step_surge_filter(self, candles, symbol, threshold=1.0, period=14, window=30, range_multiplier=3.0, start_time=None, end_time=None, timezone='KST'):
        """
        3개 연속 양봉 + 거래량 급증 패턴 찾기 + 가격 변동폭 확인
        
        조건:
        1. 3개의 연속된 캔들이 모두 양봉 (종가 > 시가)
        2. 3개의 캔들 모두 14개 평균 거래량을 넘음
        3. 최근 window개 캔들 또는 지정된 시간대 내에서 이런 패턴이 있는지 확인
        
        Args:
            candles: 캔들 데이터 리스트 [(open_time, open, high, low, close, volume, quote_volume), ...]
            symbol: 확인할 심볼 - 로깅용
            threshold: 거래량 임계값 배수 (기본값: 1.0 = 평균 이상)
            period: 평균 계산 기간 (기본값: 14)
            window: 검사할 캔들 윈도우 (기본값: 30) - start_time이 None일 때 사용
            range_multiplier: 가격 변동폭 배수 (기본값: 3.0 = 직전 캔들 대비 3배)
            start_time: 시작 시간 (datetime 객체 또는 'YYYY-MM-DD HH:MM:SS' 문자열) - 설정 시 window 무시
            end_time: 종료 시간 (datetime 객체 또는 'YYYY-MM-DD HH:MM:SS' 문자열) - start_time과 함께 사용
            timezone: 'KST' (한국시간, 기본값) 또는 'UTC' (세계시) - start_time 사용 시만 적용
        
        Returns:
            pattern_time: 패턴 발견 시 시작 시간 문자열, 없으면 False
        """
        from datetime import datetime, timedelta
        
        # 시간대 모드 vs 윈도우 모드
        use_timerange = start_time is not None and end_time is not None
        
        if use_timerange:
            # 시간대 모드
            # 문자열을 datetime으로 변환
            if isinstance(start_time, str):
                start_time = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            if isinstance(end_time, str):
                end_time = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            
            # KST → UTC 변환 (DB는 UTC로 저장됨)
            if timezone.upper() == 'KST':
                print(f"\n🔍 {symbol} 시간대 필터링 (KST → UTC 변환)")
                print(f"   입력 시간 (KST): {start_time} ~ {end_time}")
                start_time_utc = start_time - timedelta(hours=9)
                end_time_utc = end_time - timedelta(hours=9)
                print(f"   변환 시간 (UTC): {start_time_utc} ~ {end_time_utc}")
            else:
                start_time_utc = start_time
                end_time_utc = end_time
                print(f"\n🔍 {symbol} 시간대 필터링 (UTC)")
                print(f"   기간: {start_time_utc} ~ {end_time_utc}")
            
            # 데이터 충분성 확인
            if len(candles) < period + 3:
                print(f"⚠️ {symbol}: 데이터가 부족합니다. (필요: {period + 3}개, 현재: {len(candles)}개)")
                return False
            
            # 시간대 내의 캔들만 필터링
            time_range_candles = []
            for candle in candles:
                candle_time = candle[0]
                # datetime 객체가 아니면 변환
                if not isinstance(candle_time, datetime):
                    candle_time = datetime.fromtimestamp(int(candle_time) / 1000)
                
                if start_time_utc <= candle_time <= end_time_utc:
                    time_range_candles.append(candle)
            
            if len(time_range_candles) == 0:
                print(f"⚠️ {symbol}: 지정된 시간대({start_time} ~ {end_time})에 데이터가 없습니다.")
                return False
            
            print(f"📊 {symbol}: 시간대 내 {len(time_range_candles)}개 캔들 발견")
            
            # 시간대 내 캔들 검사 (최소 3개 필요)
            if len(time_range_candles) < 3:
                print(f"⚠️ {symbol}: 시간대 내 캔들이 부족합니다. (최소 3개 필요, 현재: {len(time_range_candles)}개)")
                return False
            
            # 전체 candles에서 시간대 캔들의 시작 인덱스 찾기
            first_time_candle = time_range_candles[0]
            start_idx_in_all = candles.index(first_time_candle)
            
            recent_candles = time_range_candles
            base_idx_offset = start_idx_in_all
        else:
            # 윈도우 모드 (기존 방식)
            if len(candles) < window + period:
                # 데이터가 충분하지 않으면 False
                return False
            
            # 최근 window개 캔들만 사용 (나머지는 평균 계산용)
            recent_candles = candles[-window:]
            base_idx_offset = len(candles) - window
        
        # window 또는 시간대 내에서 연속 3개 캔들 검사
        for i in range(len(recent_candles) - 2):
            # 연속 3개 캔들
            candle1 = recent_candles[i]
            candle2 = recent_candles[i + 1]
            candle3 = recent_candles[i + 2]
            
            # 1. 양봉 체크 (종가 > 시가)
            is_bullish1 = float(candle1[4]) > float(candle1[1])  # close > open
            is_bullish2 = float(candle2[4]) > float(candle2[1])
            is_bullish3 = float(candle3[4]) > float(candle3[1])
            
            if not (is_bullish1 and is_bullish2 and is_bullish3):
                continue  # 3개 모두 양봉이 아니면 스킵
            
            # 2. 각 캔들의 거래량 체크
            # 전체 candles에서의 실제 인덱스
            actual_idx = base_idx_offset + i
            
            if actual_idx < period:
                continue  # 평균 계산에 필요한 이전 데이터가 부족
            
            # candle1 이전 period개 캔들로 평균 계산
            avg_candles1 = candles[actual_idx - period:actual_idx]
            if len(avg_candles1) < period:
                continue
            
            avg_volume1 = sum(float(c[5]) for c in avg_candles1) / len(avg_candles1)
            volume1 = float(candle1[5])
            volume2 = float(candle2[5])
            volume3 = float(candle3[5])
            
            # 3개 모두 평균 거래량 이상인지 체크
            volume_check1 = volume1 >= avg_volume1 * threshold
            volume_check2 = volume2 >= avg_volume1 * threshold
            volume_check3 = volume3 >= avg_volume1 * threshold
            
            if not (volume_check1 or volume_check2 or volume_check3):
                continue  # 거래량 조건 미달
            
            # 3. 가격 변동폭 체크 (3개 캔들 직전 캔들 대비)
            if actual_idx == 0:
                continue
            
            previous_candle = candles[actual_idx - 1]
            previous_range = float(previous_candle[2]) - float(previous_candle[3])  # high - low
            
            # 3개 캔들의 가격 변동폭
            range1 = float(candle1[2]) - float(candle1[3])  # high - low
            range2 = float(candle2[2]) - float(candle2[3])
            range3 = float(candle3[2]) - float(candle3[3])
            
            # 최소 1개의 캔들이라도 직전 캔들의 range_multiplier배 이상 변동폭을 가져야 함
            has_large_range = (range1 >= previous_range * range_multiplier) or (range2 >= previous_range * range_multiplier) or (range3 >= previous_range * range_multiplier)
            
            if not has_large_range:
                continue  # 가격 변동폭 조건 미달
            
            if volume_check1 and volume_check2 and volume_check3:
                # 패턴 발견!
                position = len(recent_candles) - i - 3  # 현재부터 몇 개 전인지
                
                # 첫 번째 캔들의 시작 시간 (UTC → KST 변환)
                if isinstance(candle1[0], datetime):
                    pattern_time_utc = candle1[0]
                else:
                    pattern_time_utc = datetime.fromtimestamp(int(candle1[0]) / 1000)
                
                # UTC → KST 변환 (+9시간)
                from datetime import timedelta
                pattern_time_kst = pattern_time_utc + timedelta(hours=9)
                pattern_time = pattern_time_kst.strftime('%Y-%m-%d %H:%M')
                
                if use_timerange:
                    print(f"🔥🔥🔥 {symbol}: 시간대 내 3연속 양봉+거래량 급증 패턴 발견! [시작: {pattern_time} KST]")
                    print(f"   위치: 시간대 시작부터 {i}개 후")
                else:
                    print(f"🔥🔥🔥 {symbol}: 3연속 양봉+거래량 급증 패턴 발견! [시작: {pattern_time} KST]")
                    print(f"   위치: 최근 캔들에서 {position}개 전")
                
                print(f"   직전 캔들 변동폭: {previous_range:.4f}")
                if previous_range == 0:
                    previous_range = 0.0001  # 0 나누기 방지
                print(f"   캔들1: 가격 {float(candle1[1]):.4f}→{float(candle1[4]):.4f}, 변동폭 {range1:.4f} ({range1/previous_range:.2f}x), 거래량 {volume1:.2f} ({volume1/avg_volume1:.2f}x)")
                print(f"   캔들2: 가격 {float(candle2[1]):.4f}→{float(candle2[4]):.4f}, 변동폭 {range2:.4f} ({range2/previous_range:.2f}x), 거래량 {volume2:.2f} ({volume2/avg_volume1:.2f}x)")
                print(f"   캔들3: 가격 {float(candle3[1]):.4f}→{float(candle3[4]):.4f}, 변동폭 {range3:.4f} ({range3/previous_range:.2f}x), 거래량 {volume3:.2f} ({volume3/avg_volume1:.2f}x)")
                return pattern_time
        
        if use_timerange:
            print(f"⚠️ {symbol}: 지정된 시간대 내에서 패턴을 찾지 못했습니다.")
        
        return False
    
    def _high_volume_spike_filter(self, candles, symbol, period=14, window=30, volume_range_multiplier=5.0):
        """
        거래량 급등 패턴 찾기
        
        조건:
        1. 하나의 캔들의 거래량이 14개 거래량 이동평균(MA)보다 volume_range_multiplier배 이상
        2. 최근 window개 캔들 내에서 이런 패턴이 있는지 확인
        
        Args:
            candles: 캔들 데이터 리스트 [(open_time, open, high, low, close, volume, quote_volume), ...]
            symbol: 확인할 심볼 - 로깅용
            period: 이동평균 계산 기간 (기본값: 14)
            window: 검사할 캔들 윈도우 (기본값: 30)
            volume_range_multiplier: 거래량 배수 (기본값: 5.0 = MA 대비 5배)
        
        Returns:
            pattern_time: 패턴 발견 시 시작 시간 문자열, 없으면 False
        """
        from datetime import datetime, timedelta
        
        # 데이터 충분성 확인
        if len(candles) < window + period:
            return False
        
        # 최근 window개 캔들만 사용
        recent_candles = candles[-window:]
        base_idx_offset = len(candles) - window
        
        # window 내에서 각 캔들 검사
        for i in range(len(recent_candles)):
            candle = recent_candles[i]
            actual_idx = base_idx_offset + i
            
            # 이동평균 계산에 필요한 이전 데이터가 충분한지 확인
            if actual_idx < period:
                continue
            
            # 현재 캔들 이전 period개의 거래량으로 단순 이동평균(SMA) 계산
            prev_volumes = [float(candles[j][5]) for j in range(actual_idx - period, actual_idx)]
            avg_volume = sum(prev_volumes) / len(prev_volumes)
            
            # 현재 캔들의 거래량
            current_volume = float(candle[5])
            
            # 양봉 체크 (종가 > 시가)
            is_bullish = float(candle[4]) > float(candle[1])
            
            if not is_bullish:
                continue  # 양봉이 아니면 스킵
            
            # 거래량 급등 체크
            if current_volume >= avg_volume * volume_range_multiplier:
                # 패턴 발견!
                position = len(recent_candles) - i - 1  # 현재부터 몧 개 전인지
                
                # 캔들의 시작 시간 (UTC → KST 변환)
                if isinstance(candle[0], datetime):
                    pattern_time_utc = candle[0]
                else:
                    pattern_time_utc = datetime.fromtimestamp(int(candle[0]) / 1000)
                
                # UTC → KST 변환 (+9시간)
                pattern_time_kst = pattern_time_utc + timedelta(hours=9)
                pattern_time = pattern_time_kst.strftime('%Y-%m-%d %H:%M')
                
                print(f"📈 {symbol}: 거래량 급등 패턴 발견! [시간: {pattern_time} KST]")
                print(f"   위치: 최근 캔들에서 {position}개 전")
                print(f"   MA{period} 거래량: {avg_volume:.2f}")
                print(f"   현재 거래량: {current_volume:.2f} ({current_volume/avg_volume:.2f}x)")
                print(f"   가격: {float(candle[1]):.4f}→{float(candle[4]):.4f}")
                
                return pattern_time
        
        return False