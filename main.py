"""Deterministic launch-day Twitch viewer forecasts using only the standard library."""

import json
import math
import os
from pathlib import Path


INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)
BASELINE_Z = (-1.645, -0.674, 0.0, 0.674, 1.645)


def _median(values):
    values = sorted(values)
    if not values:
        return 0.0
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def _weighted_quantile(samples, level):
    """Left-continuous weighted empirical quantile of (value, weight) pairs."""
    ordered = sorted(samples, key=lambda item: item[0])
    total = sum(weight for _, weight in ordered)
    if not ordered or total <= 0:
        return 0.0
    threshold = level * total
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= threshold:
            return value
    return ordered[-1][0]


def _history_context(case, anchor):
    """Summarize the category's pre-checkpoint level and short-term movement."""
    date = case["day_start"][:10]
    reference_day = _previous_date(date)
    prior_day = []
    prior_values = []
    for row in case.get("history_hourly") or []:
        stamp = row.get("from", "")
        value = row.get("viewers")
        if value is None or value <= 0 or stamp >= case["checkpoint"]:
            continue
        prior_values.append(float(value))
        if stamp[:10] == reference_day:
            prior_day.append(float(value))

    # Exclude hour one itself: it is the launch observation being forecast,
    # not a pre-launch reference level.
    reference = _median(prior_day)
    if not reference and prior_values:
        reference = _median([v for row in case.get("history_hourly") or []
                             if row.get("viewers") is not None and row.get("viewers") > 0
                             and row.get("from", "")[:10] != date
                             and row.get("from", "") < case["checkpoint"]
                             for v in [float(row["viewers"])]] )
    uplift = math.log(max(anchor, 1.0) / max(reference, 1.0)) if reference else 0.0

    points = []
    for row in case.get("history_hourly") or []:
        value = row.get("viewers")
        if value is not None and value > 0 and row.get("from", "") < case["checkpoint"]:
            points.append(float(value))
    recent = points[-5:]
    if len(recent) >= 2:
        slopes = [math.log(max(b, 1.0) / max(a, 1.0)) for a, b in zip(recent, recent[1:])]
        momentum = _median(slopes)
    else:
        momentum = 0.0
    return uplift, momentum


def _comparable_profiles(case):
    """Get complete release-day viewer curves, excluding GTA VI's teaser history."""
    profiles = []
    for launch in case.get("comparables") or []:
        name = launch.get("name", "")
        if "grand theft auto vi" in name.lower():
            continue
        day = launch.get("day_start", "")[:10]
        if not day:
            continue
        previous_day = _previous_date(day)
        by_hour = {}
        previous_day_values = []
        for point in launch.get("hourly") or []:
            stamp = point.get("from", "")
            viewers = point.get("viewers")
            if viewers is None or viewers < 0:
                continue
            if stamp[:10] == day:
                try:
                    hour = int(stamp[11:13])
                except (ValueError, IndexError):
                    continue
                if 0 <= hour < 24:
                    by_hour[hour] = max(1.0, float(viewers))
            elif stamp[:10] == previous_day:
                previous_day_values.append(float(viewers))
        if 0 not in by_hour or len(by_hour) < 20:
            continue
        # A sparse launch-day curve is not interpolated: omit that donor.
        if any(hour not in by_hour for hour in range(24)):
            continue
        channels = None
        for point in launch.get("hourly") or []:
            if point.get("from", "")[:10] == day and point.get("from", "")[11:13] == "00":
                channels = point.get("channels")
                break
        reference = _median(previous_day_values)
        profiles.append({
            "name": name,
            "viewers": [by_hour[h] for h in range(24)],
            "channels": max(1.0, float(channels or 1)),
            "uplift": math.log(by_hour[0] / max(reference, 1.0)) if reference else 0.0,
        })
    return profiles


def _previous_date(day):
    # YYYY-MM-DD arithmetic without importing date parsing machinery.
    import datetime
    return (datetime.date.fromisoformat(day) - datetime.timedelta(days=1)).isoformat()


def _fallback_quantiles(anchor, hour):
    spread = 0.15 * math.sqrt(max(1, hour - 1))
    return [max(1.0, anchor * math.exp(z * spread)) for z in BASELINE_Z]


def _forecast_case(case):
    if case.get("levels") != list(LEVELS):
        raise ValueError("unexpected quantile levels")
    known = next(row for row in case["known"] if row.get("hour") == 1)
    anchor = max(1.0, float(known["viewers"]))
    anchor_channels = max(1.0, float(known.get("channels") or 1))
    context_uplift, context_momentum = _history_context(case, anchor)
    profiles = _comparable_profiles(case)

    forecast = []
    for row in case["forecast"]:
        hour = int(row["hour"])
        if not profiles:
            quantiles = _fallback_quantiles(anchor, hour)
        else:
            weighted_curves = []
            for profile in profiles:
                first = profile["viewers"][0]
                # Bandwidth 0.85 was selected by leave-one-launch-out checks.
                distance = abs(math.log(first) - math.log(anchor)) / 0.85
                # Channel density and the category's recent pre-launch uplift
                # have small weights: they add context without overpowering
                # the more reliable hour-one audience match.
                density_target = anchor / anchor_channels
                density_donor = first / profile["channels"]
                distance += 0.025 * min(4.0, abs(math.log(density_target / density_donor)))
                distance += 0.02 * min(4.0, abs(context_uplift - profile["uplift"]))
                weight = math.exp(-min(40.0, distance))
                ratio = math.log(profile["viewers"][hour - 1] / first)
                weighted_curves.append((ratio, weight))

            # Momentum is deliberately only a small correction. The recent
            # trend is derived from the target category's own history, and is
            # capped so a noisy pre-launch hour cannot dominate the analogs.
            quantile_logs = [_weighted_quantile(weighted_curves, q) for q in LEVELS]
            momentum_adjustment = max(-0.12, min(0.12, 0.04 * context_momentum * math.sqrt(hour - 1)))
            quantiles = [anchor * math.exp(value + momentum_adjustment) for value in quantile_logs]

        # Keep the schema valid even with extreme or malformed source values.
        row_q = []
        for value in quantiles:
            if not math.isfinite(value):
                value = 1.0
            row_q.append(min(1_000_000_000.0, max(1.0, value)))
        row_q.sort()
        forecast.append({"hour": hour, "q": row_q})
    return {"hours": forecast}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = _forecast_case(case)
        (OUTPUT_DIR / (path.stem + ".out")).write_text(
            json.dumps(result, separators=(",", ":"), allow_nan=False) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
