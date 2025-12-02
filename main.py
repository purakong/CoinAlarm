"""
CoinAlarm - 거래량 급증 모니터링 시스템

프로젝트 루트 실행 파일
"""

import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.api_server import app
import uvicorn

if __name__ == "__main__":
    print("🚀 CoinAlarm 서버 시작...")
    print("📍 웹 페이지: http://localhost:8000")
    print("📍 API: http://localhost:8000/api/surge")
    print("📁 데이터 저장: data/surge_results.json")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
