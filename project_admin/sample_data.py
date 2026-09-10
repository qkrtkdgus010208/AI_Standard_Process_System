from pathlib import Path
import sys

from db.database_manager import DatabaseManager


def _verify_root_execution() -> None:
    """프로젝트 최상위 루트 디렉토리에서 실행되었는지 검증합니다."""
    project_root = Path(__file__).resolve().parent.parent
    current_dir = Path.cwd().resolve()
    if current_dir != project_root:
        sys.stderr.write(
            f"\n❌ [실행 오류] 샘플 데이터 생성은 반드시 프로젝트 최상위 루트 디렉토리에서 실행해야 합니다.\n"
            f"   현재 위치: {current_dir}\n"
            f"   프로젝트 루트: {project_root}\n\n"
            f"👉 실행 방법:\n"
            f"   cd {project_root}\n"
            f"   python3 project_admin/sample_data.py\n\n"
        )
        sys.exit(1)


def create_sample_data() -> None:
    """관리자, 직원, 작업 이력을 테스트 DB에 중복 없이 추가합니다."""
    database_manager = DatabaseManager()
    database_manager.initialize_database()
    database_manager.insert_sample_data()
    print("샘플 데이터 생성 완료")
    print("관리자 ID: admin")
    print("관리자 Password: admin1234")


if __name__ == "__main__":
    _verify_root_execution()
    create_sample_data()
