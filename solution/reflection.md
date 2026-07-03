# Reflection

The hardest faults for me were the subtle AI-infrastructure and lineage cases.
The obvious contract, freshness, schema, and type failures can be caught with
the published baseline limits, but private scoring is expected to include more
near-boundary drift. For that reason, I used the baseline constants as hard
guards and added narrower soft thresholds for signals such as feature skew,
embedding centroid shift, stale corpora, delayed batches, and long lineage runs.
For lineage graph shape, I also keep a small in-run modal count for upstream and
downstream edges so a missing edge or orphaned output can be caught even when
runtime is not extreme.

My cost/coverage tradeoff is intentionally coverage-first. On practice, this
defense reached full catch rate with no cost overage; on public, it still caught
all reported faults but spent more than the budget because every event is
profiled with the relevant metered tool. I kept that tradeoff because the score
penalizes a missed fault more heavily than a small cost overage, and the private
phase is described as having harder subtle faults. If I had another pass, I
would add a learned budget policy that skips only low-risk repeated event
families near the end of the stream, but I would not blindly reduce tool calls
without evidence because that would likely hurt private TPR.

Validation:

```bash
.venv/bin/python3 harness/selfcheck.py
.venv/bin/python3 harness/run.py --phase practice --defense solution/defense.py --out solution/practice_report.json
.venv/bin/python3 harness/run.py --phase public --defense solution/defense.py --out solution/public_report.json
```
