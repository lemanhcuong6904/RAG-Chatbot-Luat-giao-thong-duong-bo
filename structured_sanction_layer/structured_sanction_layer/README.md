# Structured Sanction Layer – Luật giao thông đường bộ

Generated from the supplied Markdown files only.

## Scope

- Luật 35/2024/QH15, Luật 36/2024/QH15 (2 source files nhưng 1 logical document), NĐ 165/2024/NĐ-CP: indexed into `legal_provisions.jsonl` as legal context/definitions.
- NĐ 168/2024/NĐ-CP: primary sanction source; rules extracted from Articles 6–40.
- NĐ 238/2026/NĐ-CP: amendment overlay with versioned rules and amendment events. Its general effective date is **2026-08-15**, so on **2026-08-11** the amended versions are future rules.

## Outputs

- `sanction_rules.jsonl` / `sanction_rules.csv`: versioned structured sanction rules.
- `sanctions.sqlite`: query-ready database.
- `sanction_amendments.jsonl`: amendment/repeal/addition operations from NĐ 238.
- `sanction_crossrefs.jsonl`: edges that join fine behaviors to point deduction/additional/remedial clauses.
- `review_queue.jsonl`: cases that should not be silently trusted.
- `source_registry.jsonl`, `legal_provisions.jsonl`, `schema.json`, `metrics.json`.

## Metrics

```json
{
  "source_files": 6,
  "logical_documents": 5,
  "legal_provisions": 285,
  "sanction_rule_versions": 818,
  "fine_rules": 798,
  "warning_rules": 2,
  "confiscation_rules": 18,
  "rules_with_points": 256,
  "rules_with_suspension": 22,
  "amendment_events": 52,
  "crossref_edges": 571,
  "review_items": 2,
  "pass_rules": 816,
  "review_rules": 2,
  "effective_on_2026_08_11": 756,
  "effective_on_2026_08_15_without_deferred_scope": 762
}
```

## Temporal lookup

Use event date, not detection date. NĐ 238 Article 21 states violations occurring and ending before 2026-08-15 are handled under the decree effective at the time of the violation.

```sql
SELECT * FROM sanction_rules
WHERE behavior_code = ?
  AND (valid_from IS NULL OR valid_from <= :event_date)
  AND (valid_to IS NULL OR :event_date < valid_to);
```

Then enforce `deferred_effective_from`/`deferred_scope_text` for special 2028/2029 provisions.

## Important QA note

`behavior_code` is generated deterministically from legal wording; it is not yet a hand-curated semantic ontology. For production, maintain a separate alias/catalog layer mapping user phrases such as “vượt đèn đỏ” to the stable rule/behavior codes.
