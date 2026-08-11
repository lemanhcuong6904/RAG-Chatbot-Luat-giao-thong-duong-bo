from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from rag_luat_gt.config import SANCTION_DB_PATH
from rag_luat_gt.sanction.schemas import SanctionLookup, SanctionRule
from rag_luat_gt.text import normalize_text, strip_accents


JSON_FIELDS = {
    "vehicle_codes_json": "vehicle_codes",
    "conditions_json": "conditions",
    "additional_sanctions_json": "additional_sanctions",
    "remedial_measures_json": "remedial_measures",
    "notes_json": "notes",
}


class SanctionRepository:
    def __init__(self, db_path: Path = SANCTION_DB_PATH) -> None:
        self.db_path = db_path

    def available(self) -> bool:
        return self.db_path.exists()

    def lookup(
        self,
        *,
        event_date: str,
        vehicle_code: str | None = None,
        behavior_code: str | None = None,
        behavior_contains: str | None = None,
        article: str | None = None,
        clause: str | None = None,
        point: str | None = None,
        limit: int = 20,
    ) -> SanctionLookup:
        if not self.available():
            return SanctionLookup(status="UNAVAILABLE", warnings=[f"Sanction DB not found: {self.db_path}"])

        if not vehicle_code:
            return SanctionLookup(
                status="AMBIGUOUS",
                missing_fields=["vehicle_code"],
                warnings=["Câu hỏi xử phạt chưa xác định rõ loại phương tiện."],
            )

        where = [
            "(valid_from IS NULL OR valid_from <= ?)",
            "(valid_to IS NULL OR ? < valid_to)",
            "validation_status = 'PASS'",
            "vehicle_codes_json LIKE ?",
        ]
        values: list[object] = [event_date, event_date, f'%"{vehicle_code}"%']

        if behavior_code:
            where.append("behavior_code = ?")
            values.append(behavior_code)
        elif behavior_contains:
            where.append("LOWER(behavior_text) LIKE LOWER(?)")
            values.append(f"%{behavior_contains}%")

        for field, value in [("article", article), ("clause", clause), ("point", point)]:
            if value:
                where.append(f"{field} = ?")
                values.append(value)

        sql = (
            "SELECT * FROM sanction_rules WHERE "
            + " AND ".join(where)
            + " ORDER BY CAST(article AS INTEGER), CAST(clause AS INTEGER), point LIMIT ?"
        )
        values.append(limit)

        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = [self._row_to_rule(dict(row), event_date) for row in connection.execute(sql, values)]

        if not rows:
            return SanctionLookup(status="NOT_FOUND", warnings=["Không tìm thấy sanction rule phù hợp."])
        return SanctionLookup(status="FOUND", rules=rows)

    @staticmethod
    def _row_to_rule(row: dict, event_date: str) -> SanctionRule:
        data = dict(row)
        for source_field, target_field in JSON_FIELDS.items():
            value = data.pop(source_field, None)
            if value:
                try:
                    data[target_field] = json.loads(value)
                except json.JSONDecodeError:
                    data[target_field] = []
        if data.get("deferred_effective_from") and event_date < data["deferred_effective_from"]:
            data["temporal_warning"] = (
                "Rule contains a specially deferred scope; inspect deferred_scope_text before applying it."
            )
        return SanctionRule(**data)


def behavior_contains_from_query(query: str) -> str | None:
    normalized = strip_accents(normalize_text(query))
    if "den" in normalized and ("do" in normalized or "tin hieu" in normalized):
        return "đèn tín hiệu giao thông"
    return None
