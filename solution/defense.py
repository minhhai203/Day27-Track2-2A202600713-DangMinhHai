"""
Your defense. Implement register(ctx) and a handler per event type.
See ../README.md for the full interface + toolkit reference, and
../RULES.md before you start.
"""
from api import Verdict


def _b(ctx, name, default=None):
    return ctx.baseline.get(name, default)


def _bad(result):
    return not isinstance(result, dict) or "error" in result


def _num(value, default=0.0):
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _between(value, lower, upper):
    return lower <= value <= upper


def _sigma_band(lower, upper, sigma_count):
    """Baseline min/max are clean mean +/- 3 sigma; shrink for subtle faults."""
    center = (lower + upper) / 2.0
    sigma = (upper - lower) / 6.0
    return center - sigma_count * sigma, center + sigma_count * sigma


def _verdict(alert, pillar, reasons, confidence=0.85):
    return Verdict(
        alert=bool(alert),
        confidence=confidence if alert else 0.25,
        reason="; ".join(reasons[:4]) if reasons else "within expected range",
        pillar=pillar,
    )


def _counter(ctx, name):
    counters = ctx.state.setdefault("counters", {})
    return counters.setdefault(name, {})


def _seen_anomalous_count(ctx, name, value, warmup=6):
    """Cheap modal-pattern check for graph-shape fields such as lineage counts."""
    counts = _counter(ctx, name)
    total = sum(counts.values())
    modal_count = None
    modal_freq = 0
    for candidate, freq in counts.items():
        if freq > modal_freq:
            modal_count = candidate
            modal_freq = freq

    anomalous = total >= warmup and modal_count is not None and value != modal_count
    counts[value] = counts.get(value, 0) + 1
    return anomalous, modal_count


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def check_data_batch(payload, ctx):
    profile = ctx.tools.batch_profile(payload["batch_id"])
    if _bad(profile):
        return _verdict(False, "checks", ["profile unavailable"])

    reasons = []
    row_count = _num(profile.get("row_count"))
    null_rate = _num(profile.get("null_rate", {}).get("customer_id"))
    mean_amount = _num(profile.get("mean_amount"))
    staleness = _num(profile.get("staleness_min"))

    row_min = _b(ctx, "row_count_min", 0.0)
    row_max = _b(ctx, "row_count_max", 10 ** 9)
    amount_min = _b(ctx, "mean_amount_min", 0.0)
    amount_max = _b(ctx, "mean_amount_max", 10 ** 9)
    null_max = _b(ctx, "null_rate_max", 1.0)
    stale_max = _b(ctx, "staleness_min_max", 10 ** 9)

    soft_row_min, soft_row_max = _sigma_band(row_min, row_max, 2.75)
    soft_amount_min, soft_amount_max = _sigma_band(amount_min, amount_max, 2.7)

    if not _between(row_count, row_min, row_max):
        reasons.append("row_count outside hard baseline")
    elif not _between(row_count, soft_row_min, soft_row_max):
        reasons.append("row_count near tail")

    if not _between(mean_amount, amount_min, amount_max):
        reasons.append("mean_amount outside hard baseline")
    elif not _between(mean_amount, soft_amount_min, soft_amount_max):
        reasons.append("mean_amount near tail")

    if null_rate > null_max:
        reasons.append("customer_id null_rate above hard baseline")
    elif null_rate > null_max * 0.96:
        reasons.append("customer_id null_rate elevated")

    if staleness > stale_max:
        reasons.append("batch staleness above hard baseline")
    elif staleness > stale_max * 0.96:
        reasons.append("batch staleness elevated")

    return _verdict(bool(reasons), "checks", reasons)


def check_contract_checkpoint(payload, ctx):
    diff = ctx.tools.contract_diff(payload["contract_id"], payload["checkpoint_batch_id"])
    if _bad(diff):
        return _verdict(False, "contracts", ["contract diff unavailable"])

    reasons = []
    freshness = _num(diff.get("freshness_delay_min"))
    violations = diff.get("violations") or []
    freshness_max = _b(ctx, "freshness_delay_max_min", 10 ** 9)

    if violations:
        reasons.append("contract violation: " + ",".join(violations))
    if freshness > freshness_max:
        reasons.append("freshness delay above hard SLA baseline")
    elif freshness > freshness_max * 0.96:
        reasons.append("freshness delay elevated")

    return _verdict(bool(reasons), "contracts", reasons)


def check_lineage_run(payload, ctx):
    graph = ctx.tools.lineage_graph_slice(payload["run_id"])
    if _bad(graph):
        return _verdict(False, "lineage", ["lineage slice unavailable"])

    reasons = []
    duration = _num(graph.get("duration_ms"))
    upstream = graph.get("actual_upstream") or []
    downstream_count = int(_num(graph.get("actual_downstream_count")))
    duration_max = _b(ctx, "lineage_duration_ms_max", 10 ** 9)

    if duration > duration_max:
        reasons.append("lineage duration above hard baseline")
    elif duration > duration_max * 0.95:
        reasons.append("lineage duration elevated")

    if isinstance(upstream, list):
        upstream_count = len(upstream)
    else:
        upstream_count = 0

    if upstream_count == 0:
        reasons.append("no upstream lineage edge")
    elif upstream_count == 1:
        reasons.append("only one upstream lineage edge")

    if downstream_count == 0:
        reasons.append("no downstream lineage output")

    up_odd, up_modal = _seen_anomalous_count(ctx, "lineage_upstream_count", upstream_count)
    down_odd, down_modal = _seen_anomalous_count(ctx, "lineage_downstream_count", downstream_count)
    if up_odd:
        reasons.append("upstream count differs from run pattern %s" % up_modal)
    if down_odd:
        reasons.append("downstream count differs from run pattern %s" % down_modal)

    return _verdict(bool(reasons), "lineage", reasons)


def check_feature_materialization(payload, ctx):
    drift = ctx.tools.feature_drift(payload["feature_view"], payload["batch_id"])
    if _bad(drift):
        return _verdict(False, "ai_infra", ["feature drift unavailable"])

    reasons = []
    shift = _num(drift.get("mean_shift_sigma"))
    shift_max = _b(ctx, "feature_mean_shift_sigma_max", 10 ** 9)

    if shift > shift_max:
        reasons.append("feature train/serve shift above hard baseline")
    elif shift > shift_max * 0.93:
        reasons.append("feature train/serve shift elevated")

    return _verdict(bool(reasons), "ai_infra", reasons)


def check_embedding_batch(payload, ctx):
    drift = ctx.tools.embedding_drift(payload["corpus"], payload["chunk_batch_id"])
    if _bad(drift):
        return _verdict(False, "ai_infra", ["embedding drift unavailable"])

    reasons = []
    centroid = _num(drift.get("centroid_shift"))
    age = _num(drift.get("avg_doc_age_days"))
    centroid_max = _b(ctx, "embedding_centroid_shift_max", 10 ** 9)
    age_max = _b(ctx, "corpus_avg_doc_age_days_max", 10 ** 9)

    if centroid > centroid_max:
        reasons.append("embedding centroid shift above hard baseline")
    elif centroid > centroid_max * 0.91:
        reasons.append("embedding centroid shift elevated")

    if age > age_max:
        reasons.append("corpus age above hard baseline")
    elif age > age_max * 0.96:
        reasons.append("corpus age elevated")

    return _verdict(bool(reasons), "ai_infra", reasons)
