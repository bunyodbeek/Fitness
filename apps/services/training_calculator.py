from __future__ import annotations

from typing import Dict, List


def calculate_training_profile_plan(*, recommended_weight: float, base_sets: int, base_reps: int, profile) -> Dict[str, dict]:
    """Return a 6-week progression payload keyed as week_1..week_6."""
    w1 = float(recommended_weight or 0)
    base_sets = int(base_sets or 0)
    base_reps = int(base_reps or 0)

    w2 = w1 * float(profile.w2_multiplier or 1)
    w3 = w1 * float(profile.w3_multiplier or 1)
    w4 = w1 * float(profile.w4_multiplier or 1)
    w5 = w1 * float(profile.w5_multiplier or 1)
    w6 = w5 * float(profile.deload_multiplier or 1)

    return {
        "week_1": {
            "weight": round(w1, 2),
            "sets": max(0, base_sets + int(profile.set_adjustment_w1 or 0)),
            "reps": max(0, base_reps + int(profile.rep_adjustment_w1 or 0)),
        },
        "week_2": {
            "weight": round(w2, 2),
            "sets": max(0, base_sets + int(profile.set_adjustment_w2 or 0)),
            "reps": max(0, base_reps + int(profile.rep_adjustment_w2 or 0)),
        },
        "week_3": {
            "weight": round(w3, 2),
            "sets": max(0, base_sets + int(profile.set_adjustment_w3 or 0)),
            "reps": max(0, base_reps + int(profile.rep_adjustment_w3 or 0)),
        },
        "week_4": {
            "weight": round(w4, 2),
            "sets": max(0, base_sets + int(profile.set_adjustment_w4 or 0)),
            "reps": max(0, base_reps + int(profile.rep_adjustment_w4 or 0)),
        },
        "week_5": {
            "weight": round(w5, 2),
            "sets": max(0, base_sets + int(profile.set_adjustment_w5 or 0)),
            "reps": max(0, base_reps + int(profile.rep_adjustment_w5 or 0)),
        },
        "week_6": {
            "weight": round(w6, 2),
            "sets": max(0, base_sets + int(profile.set_adjustment_w6 or 0)),
            "reps": max(0, base_reps + int(profile.rep_adjustment_w6 or 0)),
        },
    }


def normalize_week_plan(plan: Dict[str, dict], weeks_count: int = 6) -> List[dict]:
    weeks_count = max(1, min(6, int(weeks_count or 6)))
    normalized = []
    for week_number in range(1, weeks_count + 1):
        week_data = plan[f"week_{week_number}"]
        normalized.append(
            {
                "week_number": week_number,
                "sets": int(week_data["sets"]),
                "reps": int(week_data["reps"]),
                "weight": float(week_data["weight"]),
            }
        )
    return normalized


def recalculate_from_user_weight(*, profile, user_weight: float, base_sets: int, base_reps: int) -> Dict[str, dict]:
    """User-side recalculation endpoint/helper based on modified week-1 weight."""
    return calculate_training_profile_plan(
        recommended_weight=user_weight,
        base_sets=base_sets,
        base_reps=base_reps,
        profile=profile,
    )
