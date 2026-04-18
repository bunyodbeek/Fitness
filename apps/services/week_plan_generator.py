import math


def roundup_to_2_5(value: float) -> float:
    return math.ceil(float(value) / 2.5) * 2.5


def generate_weeks(base_sets, base_reps, base_weight, template):
    """
    Build a 6-week progression plan from week-1 baselines and ProgramTemplate rules.
    Week 6 uses the template deload multiplier.
    """
    base_sets = int(base_sets or 0)
    base_reps = int(base_reps or 0)
    base_weight = float(base_weight or 0)

    week_rules = (
        (2, template.w2_weight_multiplier, template.set_increment_w2, template.rep_increment_w2),
        (3, template.w3_weight_multiplier, template.set_increment_w3, template.rep_increment_w3),
        (4, template.w4_weight_multiplier, template.set_increment_w4, template.rep_increment_w4),
        (5, template.w5_weight_multiplier, template.set_increment_w5, template.rep_increment_w5),
        (6, template.deload_weight_multiplier, template.set_increment_w6, template.rep_increment_w6),
    )

    weeks = [
        {
            'week_number': 1,
            'sets': base_sets,
            'reps': base_reps,
            'weight': base_weight,
        }
    ]

    for week_number, weight_multiplier, set_increment, rep_increment in week_rules:
        weeks.append(
            {
                'week_number': week_number,
                'sets': max(0, base_sets + int(set_increment or 0)),
                'reps': max(0, base_reps + int(rep_increment or 0)),
                'weight': roundup_to_2_5(base_weight * float(weight_multiplier or 1)),
            }
        )

    return weeks


def generate_week_plan(w1_sets, w1_reps, w1_weight, profile, weeks_count=6):
    weeks_count = max(1, int(weeks_count or 1))
    current_sets = int(w1_sets or 0)
    current_reps = int(w1_reps or 0)
    current_weight = float(w1_weight or 0)

    output = [
        {
            'week_number': 1,
            'sets': current_sets,
            'reps': current_reps,
            'weight': current_weight,
        }
    ]

    for week_number in range(2, weeks_count + 1):
        sets_next = current_sets + int(profile.sets_increment)
        reps_next = max(6, current_reps + int(profile.reps_increment))

        cand1 = current_weight * float(profile.weight_mult_main)
        if current_weight < float(profile.weight_threshold):
            cand2 = current_weight * float(profile.weight_mult_alt)
        else:
            cand2 = current_weight + 2.5

        cand = max(cand1, cand2)
        weight_next = roundup_to_2_5(cand)
        if weight_next <= current_weight:
            weight_next = current_weight + 2.5

        output.append(
            {
                'week_number': week_number,
                'sets': int(sets_next),
                'reps': int(reps_next),
                'weight': float(weight_next),
            }
        )

        current_sets = sets_next
        current_reps = reps_next
        current_weight = weight_next

    return output
