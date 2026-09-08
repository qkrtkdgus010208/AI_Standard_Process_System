"""Product, guide, and quality summary persistence operations."""

from __future__ import annotations

from typing import Callable, Optional


class ProductRepository:
    """제품·기준 이미지·품질 기준선 저장소입니다."""

    def __init__(self, connect: Callable):
        self.connect = connect

    def search_products(self, keyword: str = "") -> list[dict]:
        """제품 검색 결과와 생산·불량 요약을 반환합니다."""
        search_text = f"%{keyword.strip()}%"
        with self.connect() as connection:
            rows = connection.execute("""SELECT p.product_id, p.product_name, p.total_steps,
                          SUM(CASE WHEN pr.completed_at IS NOT NULL THEN 1 ELSE 0 END) AS completed_count,
                          SUM(CASE WHEN pr.result = 'defect' THEN 1 ELSE 0 END) AS defect_count,
                          CASE WHEN SUM(CASE WHEN pr.completed_at IS NOT NULL THEN 1 ELSE 0 END) = 0 THEN 0.0
                            ELSE ROUND(100.0 * SUM(CASE WHEN pr.result = 'defect' THEN 1 ELSE 0 END) /
                              SUM(CASE WHEN pr.completed_at IS NOT NULL THEN 1 ELSE 0 END), 1) END AS defect_rate
                   FROM products AS p LEFT JOIN product_runs AS pr ON pr.product_id = p.product_id
                    AND pr.product_run_id > COALESCE((SELECT qb.product_run_id_cutoff FROM product_quality_baselines AS qb
                      WHERE qb.product_id = p.product_id), 0)
                   WHERE p.product_id LIKE ? OR p.product_name LIKE ?
                   GROUP BY p.product_id, p.product_name, p.total_steps ORDER BY p.product_id""", (search_text, search_text)).fetchall()
        return [dict(row) for row in rows]

    def get_product(self, product_id: str) -> Optional[dict]:
        """제품 기본 정보를 조회합니다."""
        with self.connect() as connection:
            row = connection.execute("SELECT product_id, product_name, total_steps FROM products WHERE product_id = ?", (product_id,)).fetchone()
        return dict(row) if row else None

    def get_product_step_guides(self, product_id: str) -> list[dict]:
        """제품의 STEP 기준 이미지 메타데이터를 순서대로 조회합니다."""
        with self.connect() as connection:
            rows = connection.execute("""SELECT product_id, step_no, image_path, mime_type, byte_size, sha256, updated_at
                FROM product_step_guides WHERE product_id = ? ORDER BY step_no""", (product_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_product_step_guide(self, product_id: str, step_no: int) -> Optional[dict]:
        """특정 STEP의 기준 이미지 메타데이터를 조회합니다."""
        with self.connect() as connection:
            row = connection.execute("""SELECT product_id, step_no, image_path, mime_type, byte_size, sha256, updated_at
                FROM product_step_guides WHERE product_id = ? AND step_no = ?""", (product_id, int(step_no))).fetchone()
        return dict(row) if row else None

    def replace_product_step_guides(self, product_id: str, guides: list[dict]) -> None:
        """제품의 기준 이미지 메타데이터를 한 트랜잭션으로 교체합니다."""
        product = self.get_product(product_id)
        if product is None:
            raise ValueError("기준 이미지를 등록할 제품을 찾을 수 없습니다.")
        total_steps = int(product["total_steps"])
        normalized, seen_steps = [], set()
        for guide in guides:
            step_no = int(guide["step_no"])
            if step_no < 1 or step_no > total_steps:
                raise ValueError(f"STEP {step_no}은 제품의 STEP 범위를 벗어납니다.")
            if step_no in seen_steps:
                raise ValueError(f"STEP {step_no} 기준 이미지가 중복되었습니다.")
            seen_steps.add(step_no)
            normalized.append((product_id, step_no, str(guide["image_path"]), str(guide.get("mime_type") or "image/jpeg"), int(guide.get("byte_size") or 0), str(guide.get("sha256") or "")))
        with self.connect() as connection:
            connection.execute("DELETE FROM product_step_guides WHERE product_id = ?", (product_id,))
            connection.executemany("""INSERT INTO product_step_guides(product_id, step_no, image_path, mime_type, byte_size, sha256)
                VALUES (?, ?, ?, ?, ?, ?)""", normalized)

    def create_product(self, product_id: str, product_name: str, total_steps: int) -> None:
        """제품과 전체 STEP 수를 등록합니다."""
        cleaned_id, cleaned_name = product_id.strip(), product_name.strip()
        if not cleaned_id or not cleaned_name:
            raise ValueError("제품번호와 제품명은 비어 있을 수 없습니다.")
        if int(total_steps) < 1:
            raise ValueError("전체 STEP은 1 이상이어야 합니다.")
        with self.connect() as connection:
            connection.execute("INSERT INTO products(product_id, product_name, total_steps) VALUES (?, ?, ?)", (cleaned_id, cleaned_name, int(total_steps)))

    def update_product(self, product_id: str, product_name: str, total_steps: int) -> None:
        """제품명과 전체 STEP 수를 수정합니다."""
        cleaned_name = product_name.strip()
        if not cleaned_name:
            raise ValueError("제품명은 비어 있을 수 없습니다.")
        if int(total_steps) < 1:
            raise ValueError("전체 STEP은 1 이상이어야 합니다.")
        with self.connect() as connection:
            cursor = connection.execute("UPDATE products SET product_name = ?, total_steps = ? WHERE product_id = ?", (cleaned_name, int(total_steps), product_id))
            if cursor.rowcount == 0:
                raise ValueError("수정할 제품을 찾을 수 없습니다.")
            connection.execute("DELETE FROM product_step_guides WHERE product_id = ? AND step_no > ?", (product_id, int(total_steps)))

    def delete_product(self, product_id: str) -> None:
        """제품과 연결된 기준선·기준 이미지를 삭제합니다."""
        with self.connect() as connection:
            connection.execute("DELETE FROM product_step_guides WHERE product_id = ?", (product_id,))
            connection.execute("DELETE FROM product_quality_baselines WHERE product_id = ?", (product_id,))
            cursor = connection.execute("DELETE FROM products WHERE product_id = ?", (product_id,))
            if cursor.rowcount == 0:
                raise ValueError("삭제할 제품을 찾을 수 없습니다.")

    def get_product_step_quality_summary(self, product_id: str) -> list[dict]:
        """제품의 STEP별 검사·수동 불량 요약을 반환합니다."""
        product = self.get_product(product_id)
        if product is None:
            raise ValueError("제품을 찾을 수 없습니다.")
        baseline = self.get_product_quality_baseline(product_id)
        judgement_cutoff = int(baseline["judgement_id_cutoff"]) if baseline else 0
        defect_cutoff = int(baseline["defect_id_cutoff"]) if baseline else 0
        with self.connect() as connection:
            judgement_rows = connection.execute("""SELECT sr.step_no, COUNT(*) AS judgement_count,
                SUM(CASE WHEN jl.result = 'pass' THEN 1 ELSE 0 END) AS pass_count,
                SUM(CASE WHEN jl.result = 'fail' THEN 1 ELSE 0 END) AS fail_count,
                ROUND(100.0 * SUM(CASE WHEN jl.result = 'fail' THEN 1 ELSE 0 END) / COUNT(*), 1) AS fail_rate,
                MAX(CASE WHEN jl.result = 'fail' THEN jl.judged_at END) AS latest_fail_at
                FROM judgement_logs AS jl JOIN step_runs AS sr ON sr.step_run_id = jl.step_run_id
                JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id
                WHERE pr.product_id = ? AND jl.judgement_id > ? GROUP BY sr.step_no ORDER BY sr.step_no""", (product_id, judgement_cutoff)).fetchall()
            defect_rows = connection.execute("""SELECT sr.step_no, COUNT(*) AS defect_button_count, MAX(dl.defect_at) AS latest_defect_at
                FROM defect_logs AS dl JOIN step_runs AS sr ON sr.step_run_id = dl.step_run_id
                JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id
                WHERE pr.product_id = ? AND dl.defect_id > ? GROUP BY sr.step_no ORDER BY sr.step_no""", (product_id, defect_cutoff)).fetchall()
        by_step = {int(row["step_no"]): dict(row) for row in judgement_rows}
        for row in defect_rows:
            step_no = int(row["step_no"])
            by_step.setdefault(step_no, {"step_no": step_no, "judgement_count": 0, "pass_count": 0, "fail_count": 0, "fail_rate": 0.0, "latest_fail_at": None})
            by_step[step_no]["defect_button_count"] = int(row["defect_button_count"])
            by_step[step_no]["latest_defect_at"] = row["latest_defect_at"]
        result = []
        for step_no in range(1, int(product["total_steps"]) + 1):
            item = by_step.get(step_no, {"step_no": step_no, "judgement_count": 0, "pass_count": 0, "fail_count": 0, "fail_rate": 0.0, "latest_fail_at": None})
            item.setdefault("defect_button_count", 0)
            item.setdefault("latest_defect_at", None)
            result.append(item)
        return result

    def get_product_quality_baseline(self, product_id: str) -> Optional[dict]:
        """제품 품질 집계의 마지막 초기화 기준을 조회합니다."""
        with self.connect() as connection:
            row = connection.execute("""SELECT product_id, reset_at, product_run_id_cutoff, judgement_id_cutoff, defect_id_cutoff
                FROM product_quality_baselines WHERE product_id = ?""", (product_id,)).fetchone()
        return dict(row) if row else None

    def reset_product_quality_baseline(self, product_id: str) -> str:
        """과거 이력을 보존하고 현재 ID 이후부터 품질을 집계합니다."""
        with self.connect() as connection:
            product = connection.execute("SELECT 1 FROM products WHERE product_id = ?", (product_id,)).fetchone()
            if product is None:
                raise ValueError("제품을 찾을 수 없습니다.")
            active_run = connection.execute("SELECT 1 FROM product_runs WHERE product_id = ? AND completed_at IS NULL LIMIT 1", (product_id,)).fetchone()
            if active_run is not None:
                raise ValueError("진행 중인 제품 작업이 있어 품질 집계를 초기화할 수 없습니다.")
            product_run_cutoff = connection.execute("SELECT COALESCE(MAX(product_run_id), 0) FROM product_runs WHERE product_id = ?", (product_id,)).fetchone()[0]
            judgement_cutoff = connection.execute("""SELECT COALESCE(MAX(jl.judgement_id), 0) FROM judgement_logs AS jl
                JOIN step_runs AS sr ON sr.step_run_id = jl.step_run_id JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id
                WHERE pr.product_id = ?""", (product_id,)).fetchone()[0]
            defect_cutoff = connection.execute("""SELECT COALESCE(MAX(dl.defect_id), 0) FROM defect_logs AS dl
                JOIN step_runs AS sr ON sr.step_run_id = dl.step_run_id JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id
                WHERE pr.product_id = ?""", (product_id,)).fetchone()[0]
            connection.execute("""INSERT OR REPLACE INTO product_quality_baselines(product_id, reset_at, product_run_id_cutoff, judgement_id_cutoff, defect_id_cutoff)
                VALUES (?, datetime('now', '+9 hours'), ?, ?, ?)""", (product_id, product_run_cutoff, judgement_cutoff, defect_cutoff))
            reset_at = connection.execute("SELECT reset_at FROM product_quality_baselines WHERE product_id = ?", (product_id,)).fetchone()["reset_at"]
        return str(reset_at)
