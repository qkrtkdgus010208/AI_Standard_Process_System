"""개발용 샘플 데이터를 수동으로 생성하는 독립 실행 파일입니다."""

from database_manager import DatabaseManager


def create_sample_data() -> None:
    """관리자, 직원, 작업 이력을 테스트 DB에 중복 없이 추가합니다."""
    database_manager = DatabaseManager()
    database_manager.initialize_database()
    database_manager.insert_sample_data()
    print("샘플 데이터 생성 완료")
    print("관리자 ID: admin")
    print("관리자 Password: admin1234")


if __name__ == "__main__":
    create_sample_data()
