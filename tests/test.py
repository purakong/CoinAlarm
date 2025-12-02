from downloader import ChartDownloader
from service.filter import Filter

def main():
    print("=" * 50)
    print("코인 차트 데이터 다운로드 및 거래량 급증 필터링")
    print("=" * 50)
    
    # 1. DB 연결 정보 설정
    # 본인의 MySQL 설정에 맞게 수정하세요!
    db_config = {
        'host': 'localhost',      # MySQL 서버 주소 (보통 localhost)
        'user': 'root',           # MySQL 사용자 이름
        'password': '1234',       # MySQL 비밀번호 (본인이 설정한 것으로 변경!)
        'database': 'coin_chart'  # 사용할 데이터베이스 이름
    }
    
    # 2. 필요 객체 생성
    # DB에 자동으로 연결됩니다
    downloader = ChartDownloader(db_config)
    filter = Filter(db_config)
    
    # 3. 바이낸스 상장 리스트 가져오기
    symbols = downloader.get_all_usdt_symbols()

    # 3. 여러 코인의 데이터를 다운로드
    for symbol in symbols:
        print(f"\n{'='*50}")
        # 첫 다운로드: 1000개의 캔들 데이터를 가져옴
        # 이미 데이터가 있으면: 최신 데이터만 업데이트
        downloader.download_and_save(
            symbol=symbol,
            timeframe='5m',
            initial_limit=300  # 처음 다운로드할 캔들 개수
        )
        
    for symbol in symbols:
        print(f"\n{'='*50}")
        # 첫 다운로드: 1000개의 캔들 데이터를 가져옴
        # 이미 데이터가 있으면: 최신 데이터만 업데이트
        downloader.download_and_save(
            symbol=symbol,
            timeframe='15m',
            initial_limit=300  # 처음 다운로드할 캔들 개수
        )
    
    # 4. DB에서 데이터 조회 예제
    print(f"\n{'='*50}")
    print("📊 DB에서 거래량 급증 필터링 시작")
    print(f"{'='*50}")

    filtered_symbols_5m = filter.filtering_symbols(
        symbols=symbols,
        time_frame='5m',
        filter_type='surge_volume',
        threshold=2.0,
        period=14
    )
    
    filtered_symbols_15m = filter.filtering_symbols(
        symbols=symbols,
        time_frame='15m',
        filter_type='surge_volume',
        threshold=2.0,
        period=14
    )    

    # 5. DB 연결 종료
    downloader.close()
    
    print(f"\n{'='*50}")

if __name__ == "__main__":
    # 메인 예제 실행
    main()
