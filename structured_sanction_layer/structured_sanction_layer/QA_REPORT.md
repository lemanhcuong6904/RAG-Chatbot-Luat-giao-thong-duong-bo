# QA Report — Structured Sanction Layer

## Structural checks

- Rule versions: **818**
- Duplicate `rule_id`: **0**
- Fine rows missing min/max or with inverted range: **0**
- PASS rules: **816**
- REVIEW rules: **2**
- Review queue items: **2**
- Logical legal documents: **5** from **6** Markdown source files.

## Golden spot-check 1 — xe mô tô không chấp hành đèn tín hiệu

```json
{
  "rule_id": "ND168_A07_K7_Pc_UNSPECIFIED_BASE",
  "behavior_text": "Không chấp hành hiệu lệnh của đèn tín hiệu giao thông",
  "fine_min": 4000000,
  "fine_max": 6000000,
  "license_points_deducted": 4,
  "valid_from": "2025-01-01",
  "valid_to": null,
  "source_location": "Điều 7, khoản 7, điểm c"
}
```

Expected structured join: fine **4,000,000–6,000,000 VND** + **4 GPLX points**, target `Điều 7, khoản 7, điểm c`.

## Golden spot-check 2 — child safety amendment boundary

At event date **2026-08-11**, the pre-amendment `Điều 6 khoản 3 điểm m` version is applicable. From **2026-08-15**, NĐ 238 splits the conduct: front-row seating remains a fine rule while failure to use a suitable child safety device becomes a warning rule (subject to the text's stated exception).

```json
[
  {
    "rule_id": "ND168_A06_K3_Pm_UNSPECIFIED_BASE",
    "primary_sanction_type": "FINE",
    "behavior_text": "Chở trẻ em dưới 10 tuổi và chiều cao dưới 1,35 mét trên xe ô tô ngồi cùng hàng ghế với người lái xe (trừ loại xe ô tô chỉ có một hàng ghế) hoặc không sử dụng thiết bị an toàn phù hợp cho trẻ em theo quy định",
    "fine_min": 800000,
    "fine_max": 1000000,
    "valid_from": "2026-01-01",
    "valid_to": "2026-08-15",
    "source_location": "Điều 6, khoản 3, điểm m"
  },
  {
    "rule_id": "ND168_A06_K1a_P__UNSPECIFIED_A238",
    "primary_sanction_type": "WARNING",
    "behavior_text": "Người điều khiển xe ô tô chở trẻ em dưới 10 tuổi và chiều cao dưới 1,35 mét trên xe mà không sử dụng thiết bị an toàn phù hợp cho trẻ em theo quy định (trừ xe ô tô kinh doanh vận tải hành khách)",
    "fine_min": null,
    "fine_max": null,
    "valid_from": "2026-08-15",
    "valid_to": null,
    "source_location": "Điều 6, khoản 1a (bổ sung bởi Điều 2 NĐ 238/2026/NĐ-CP)"
  },
  {
    "rule_id": "ND168_A06_K3_Pm_UNSPECIFIED_A238",
    "primary_sanction_type": "FINE",
    "behavior_text": "Chở trẻ em dưới 10 tuổi và chiều cao dưới 1,35 mét trên xe ô tô ngồi cùng hàng ghế với người lái xe (trừ xe ô tô chỉ có một hàng ghế)",
    "fine_min": 800000,
    "fine_max": 1000000,
    "valid_from": "2026-08-15",
    "valid_to": null,
    "source_location": "Điều 6, khoản 3, điểm m (được sửa bởi Điều 2 NĐ 238/2026/NĐ-CP)"
  }
]
```

## Golden spot-check 3 — NĐ 238 addition, Điều 20 khoản 8a

```json
{
  "rule_id": "ND168_A20_K8a_P__UNSPECIFIED_A238",
  "behavior_text": "Người điều khiển xe ô tô không kinh doanh vận tải hành khách nhưng chở người có thu tiền hoặc ký hợp đồng, nhận đặt chỗ để chở người trên xe",
  "fine_min": 12000000,
  "fine_max": 14000000,
  "license_points_deducted": 6,
  "valid_from": "2026-08-15",
  "source_location": "Điều 20, khoản 8a (bổ sung bởi Điều 7 NĐ 238/2026/NĐ-CP)"
}
```

Expected from **2026-08-15**: fine **12,000,000–14,000,000 VND** + **6 GPLX points**.

## Explicit unresolved cases

These are intentionally **not guessed** because the supplied NĐ 168 source makes their effectiveness depend on environmental-law rules not included in this six-file build:

```json
[
  {
    "type": "REQUIRES_EXTERNAL_EFFECTIVE_DATE",
    "rule_id": "ND168_A32_K1_Pb_INDIVIDUAL_BASE",
    "source_location": "Điều 32, khoản 1, điểm b",
    "deferred_scope_text": "Có hiệu lực theo pháp luật bảo vệ môi trường về kiểm định khí thải xe mô tô, xe gắn máy.",
    "text": "Đưa phương tiện không có giấy chứng nhận kiểm định khí thải xe mô tô, xe gắn máy hoặc có nhưng đã hết hạn sử dụng hoặc sử dụng giấy chứng nhận kiểm định khí thải xe mô tô, xe gắn máy không do cơ quan có thẩm quyền cấp"
  },
  {
    "type": "REQUIRES_EXTERNAL_EFFECTIVE_DATE",
    "rule_id": "ND168_A32_K1_Pb_ORGANIZATION_BASE",
    "source_location": "Điều 32, khoản 1, điểm b",
    "deferred_scope_text": "Có hiệu lực theo pháp luật bảo vệ môi trường về kiểm định khí thải xe mô tô, xe gắn máy.",
    "text": "Đưa phương tiện không có giấy chứng nhận kiểm định khí thải xe mô tô, xe gắn máy hoặc có nhưng đã hết hạn sử dụng hoặc sử dụng giấy chứng nhận kiểm định khí thải xe mô tô, xe gắn máy không do cơ quan có thẩm quyền cấp"
  }
]
```

## Temporal policy

`valid_from` is inclusive; `valid_to` is exclusive. Query by the date when the violation occurred. Rows with `deferred_effective_from` and `deferred_scope_text` require scope-aware checking because some NĐ 238 provisions have special 2028/2029 effective dates, and some are only partially deferred for named vehicle groups.
