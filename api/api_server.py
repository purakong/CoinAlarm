"""
거래량 급증 모니터링 API 서버

매 5분마다 여러 시간봉(5m, 15m, 30m, 1h)의 거래량 급증을 확인하고
결과를 웹에서 볼 수 있게 제공합니다.
"""
import os,sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../')
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from apscheduler.schedulers.background import BackgroundScheduler
from core.scanner import SurgeScanner
from datetime import datetime, timedelta
import threading

app = FastAPI(title="코인 거래량 급증 모니터")

# DB 설정 (본인 설정에 맞게 수정)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '1234',
    'database': 'coin_chart'
}

# 스캐너 생성
scanner = SurgeScanner(DB_CONFIG, result_file="data/surge_results.json", history_file="data/surge_history.json")

# 스케줄러 상태 정보
scheduler_info = {
    "next_run": None,
    "last_run": None,
    "interval_minutes": 30
}


def update_scheduler_status():
    """매 분마다 스케줄러 상태 출력"""
    while True:
        import time
        time.sleep(60)  # 1분 대기
        
        if scheduler_info["next_run"]:
            now = datetime.now()
            time_left = scheduler_info["next_run"] - now
            minutes_left = int(time_left.total_seconds() / 60)
            
            if minutes_left >= 0:
                print(f"⏰ 다음 스캔까지 {minutes_left}분 남음 (예정: {scheduler_info['next_run'].strftime('%H:%M:%S')})")
            else:
                print(f"⏰ 스캔 실행 중...")


def scan_with_update():
    """스캔 실행 + 시간 업데이트"""
    scheduler_info["last_run"] = datetime.now()
    scheduler_info["next_run"] = datetime.now() + timedelta(minutes=scheduler_info["interval_minutes"])
    
    print(f"\n{'='*60}")
    print(f"🔍 스캔 시작: {scheduler_info['last_run'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏰ 다음 스캔: {scheduler_info['next_run'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    scanner.scan()



@app.on_event("startup")
def start_scheduler():
    """
    서버 시작 시 스케줄러 설정
    """
    scheduler = BackgroundScheduler()
    
    # 매 30분마다 실행
    scheduler.add_job(scan_with_update, 'interval', minutes=scheduler_info["interval_minutes"])
    
    # 서버 시작 시 즉시 1번 실행
    scheduler_info["next_run"] = datetime.now() + timedelta(minutes=scheduler_info["interval_minutes"])
    scheduler.add_job(scan_with_update, 'date')
    
    scheduler.start()
    print(f"✅ 스케줄러 시작: 매 {scheduler_info['interval_minutes']}분마다 거래량 급증 스캔")
    
    # 백그라운드 스레드로 상태 모니터링 시작
    status_thread = threading.Thread(target=update_scheduler_status, daemon=True)
    status_thread.start()


@app.on_event("shutdown")
def shutdown_event():
    """
    서버 종료 시 정리 작업
    """
    pass


@app.get("/", response_class=HTMLResponse)
def home():
    """
    메인 페이지 - HTML 파일 반환
    """
    return FileResponse("api/templates/index.html")


@app.get("/api/status")
def get_status():
    """
    API: 서버 상태 조회
    """
    now = datetime.now()
    status_data = {
        "mode": "rest",
        "scan_interval": f"{scheduler_info['interval_minutes']} minutes",
        "current_time": now.strftime('%Y-%m-%d %H:%M:%S'),
    }
    
    if scheduler_info["last_run"]:
        status_data["last_run"] = scheduler_info["last_run"].strftime('%Y-%m-%d %H:%M:%S')
    
    if scheduler_info["next_run"]:
        status_data["next_run"] = scheduler_info["next_run"].strftime('%Y-%m-%d %H:%M:%S')
        time_left = scheduler_info["next_run"] - now
        minutes_left = int(time_left.total_seconds() / 60)
        status_data["minutes_until_next_scan"] = max(0, minutes_left)
    
    return JSONResponse(content=status_data)


@app.get("/api/surge")
def get_surge_data():
    """
    API: 거래량 급증 데이터 조회 (최신)
    """
    data = scanner.get_latest_results()
    return JSONResponse(content=data)


@app.get("/api/history")
def get_history_data(limit: int = 10):
    """
    API: 스캔 이력 조회
    
    Args:
        limit: 반환할 최대 개수 (기본값: 10)
    """
    history = scanner.get_history(limit=limit)
    return JSONResponse(content={"scans": history})


if __name__ == "__main__":
    import uvicorn
    
    print("🚀 서버 시작...")
    print("📍 웹 페이지: http://localhost:8000")
    print("📍 API: http://localhost:8000/api/surge")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
