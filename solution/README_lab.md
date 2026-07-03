# Day 27 Data Siege Lab Notes

## 1. Tôi hiểu bài lab yêu cầu gì

Lab này yêu cầu tôi đóng vai người phòng thủ cho một data pipeline. Harness sẽ
stream từng event vào `solution/defense.py`; với mỗi event tôi phải quyết định
`alert=True` nếu nghi ngờ fault, hoặc `alert=False` nếu event sạch.

File được chấm chính:

```text
solution/defense.py
solution/reflection.md
solution/private_report.json
```

`private_report.json` chỉ tạo được khi phase private được mở key. Hiện tại tôi
có thể dùng practice/public để học và kiểm chứng.

## 2. Rubric/scoring tôi tối ưu

Điểm được tính theo công thức:

```text
score = 100 * (0.5 * TPR - 0.3 * FPR - 0.2 * min(cost_overage, 1))
```

Vì vậy mục tiêu của tôi là:

- Tăng `TPR`: bắt được nhiều fault thật.
- Giữ `FPR` thấp: không alert quá nhiều event sạch.
- Không vượt cost budget quá nhiều.

Một false negative thường đau hơn một false positive nhỏ, nên tôi chọn chiến
lược hơi thiên về coverage, đặc biệt vì private phase được mô tả là có nhiều
fault subtle hơn practice/public.

## 3. Các event và tool cần dùng

Mỗi handler chỉ gọi đúng tool tương ứng với event type:

```python
data_batch -> ctx.tools.batch_profile(batch_id)
contract_checkpoint -> ctx.tools.contract_diff(contract_id, checkpoint_batch_id)
lineage_run -> ctx.tools.lineage_graph_slice(run_id)
feature_materialization -> ctx.tools.feature_drift(feature_view, batch_id)
embedding_batch -> ctx.tools.embedding_drift(corpus, chunk_batch_id)
```

Tôi không đọc file, không import module ngoài allowlist, và không hardcode event
id. Logic chỉ dựa vào `ctx.tools`, `ctx.baseline`, và `ctx.state`.

## 4. Cách tôi thiết kế detector

Baseline trong `data/baselines.json` là các ngưỡng sạch theo mean +/- 3 sigma.
Tôi dùng hai lớp kiểm tra:

```python
hard_threshold = outside published baseline
soft_threshold = near baseline tail, used for subtle private faults
```

Ví dụ với batch:

```python
soft_row_min, soft_row_max = _sigma_band(row_min, row_max, 2.75)
soft_amount_min, soft_amount_max = _sigma_band(amount_min, amount_max, 2.7)
```

Nghĩa là nếu giá trị vượt baseline hard thì alert chắc chắn; nếu nằm gần đuôi
phân phối sạch thì cũng alert để bắt các lỗi subtle.

Với lineage, ngoài duration tôi thêm state nhẹ:

```python
up_odd, up_modal = _seen_anomalous_count(ctx, "lineage_upstream_count", upstream_count)
down_odd, down_modal = _seen_anomalous_count(ctx, "lineage_downstream_count", downstream_count)
```

Mục đích là phát hiện missing upstream hoặc orphan output ngay cả khi runtime
không quá cao.

## 5. Các lệnh tôi đã chạy

Tạo môi trường:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Selfcheck:

```bash
.venv/bin/python3 harness/selfcheck.py
```

Practice:

```bash
.venv/bin/python3 harness/run.py --phase practice --defense solution/defense.py --out solution/practice_report.json
```

Public:

```bash
.venv/bin/python3 harness/run.py --phase public --defense solution/defense.py --out solution/public_report.json
```

## 6. Kết quả hiện tại

Practice:

```text
score = 50.0
TPR = 1.0
FPR = 0.0
cost = 180.0 / 220.0
```

Public:

```text
score = 47.69
TPR = 1.0
FPR = 0.0165
cost = 240.0 / 220.0
```

Tôi chấp nhận public cost overage nhẹ vì detector vẫn bắt đủ fault. Nếu giảm
tool calls quá sớm, khả năng mất TPR ở private sẽ cao hơn lợi ích tiết kiệm
cost.

## 7. Việc tôi cần tự làm khi private phase mở

Khi `phases/private.key` được release, tôi chạy:

```bash
bash solution/run_private.sh
```

Sau đó kiểm tra đủ file nộp:

```bash
ls solution/defense.py solution/reflection.md solution/private_report.json submission/manifest.json screenshot/private_report_json.png
```

Cuối cùng stage/commit/push theo hướng dẫn lab:

```bash
git add solution/ submission/
git commit -m "submission"
git push
```
