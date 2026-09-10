"""관리자 계정을 제외한 모든 시스템 데이터(작업자, 제품, 작업 이력, 로그 등)를 초기화하는 독립 실행 스크립트입니다."""

import sys
from pathlib import Path

# Add project_admin to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from db.database_manager import DatabaseManager


def reset_all_data() -> None:
    """관리자 계정을 제외한 모든 데이터를 초기화합니다."""
    database_manager = DatabaseManager()
    database_manager.initialize_database()

    print("==================================================")
    print("시스템 데이터 전체 초기화 (관리자 계정 제외)")
    print("==================================================")
    counts = database_manager.wipe_all_data_except_admin()
    print("초기화 완료:")
    for key, count in counts.items():
        print(f"  · {key}: {count}건")
    print("==================================================")


if __name__ == "__main__":
    confirm = input("정말로 관리자를 제외한 모든 데이터를 초기화하시겠습니까? (yes/no): ").strip().lower()
    if confirm in ("yes", "y"):
        reset_all_data()
    else:
        print("초기화가 취소되었습니다.")
