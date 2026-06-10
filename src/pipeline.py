import sys
import os
import datetime

sys.path.append(os.path.dirname(__file__))

from apscheduler.schedulers.blocking import BlockingScheduler
from extract import extract
from transform import transform


def run_pipeline():
    print(f"\n{'='*50}")
    print(f"[{datetime.datetime.now()}] 파이프라인 시작")
    print(f"{'='*50}")

    print("\n[Step 1] 데이터 수집")
    extract()

    print("\n[Step 2] AI 분류")
    transform()

    print(f"\n{'='*50}")
    print(f"[{datetime.datetime.now()}] 파이프라인 완료")
    print(f"{'='*50}")


if __name__ == '__main__':
    # 즉시 1회 실행
    run_pipeline()

    # 이후 매 1시간마다 자동 실행
    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, 'interval', hours=1)
    print("\n스케줄러 시작! 매 1시간마다 자동 실행. 종료: Ctrl+C")
    scheduler.start()