"""
스케줄러 상태 관리

scanner.py와 api_server.py 간 순환 참조를 방지하기 위한 공유 상태
"""
from datetime import timedelta

# 스케줄러 상태 정보
scheduler_info = {
    "global": {
        "start_time": None,
        "next_run": None,
        "last_run": None,
        "interval_minutes": 30
    },
    # 필터별 스케줄 정보
    "3step_surge": {
        "start_time": None,
        "elapsed_time": timedelta(0),
        "trigger": False
    },
    "high_volume_spike": {
        "start_time": None,
        "elapsed_time": timedelta(0),
        "trigger": False
    }
}
