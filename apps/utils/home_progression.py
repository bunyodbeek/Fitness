def calculate_home_week_exercise(base_rounds, base_duration_seconds, week_number, setting):
    increments = {
        2: (setting.round_w2, setting.duration_w2, setting.rest_w2),
        3: (setting.round_w3, setting.duration_w3, setting.rest_w3),
        4: (setting.round_w4, setting.duration_w4, setting.rest_w4),
    }
    rounds = base_rounds
    duration = base_duration_seconds
    rest = setting.rest_between_rounds

    for w in range(2, week_number + 1):
        r_inc, d_inc, rest_val = increments.get(w, (0, 0, rest))
        rounds += r_inc
        duration += d_inc
        rest = rest_val

    return {
        'rounds': max(1, rounds),
        'duration_seconds': max(10, duration),
        'rest_seconds': max(15, rest),
    }
