# Calorie calculation

Single source of truth: **`apps/services/calorie_calculator.py`**. The formula is never
duplicated in views or templates.

## Layers
- **Pure formula** — `calculate_gym(exercises, timer_seconds, weight)` and
  `calculate_home(exercises, rounds, timer_seconds, weight, time_per_round_sec=None)`.
  No Django dependency; all units explicit (time in **seconds**, timer in seconds). These
  are what the unit tests exercise.
- **Model adapters** — `calories_for_gym_workout(workout, timer_seconds, profile)` and
  `calories_for_home_workout(...)` build the formula inputs from a `Workout` + `UserProfile`.

## When it runs
Server-side, on workout completion, using the **actual in-app timer** (`total_duration`
POST field, in seconds). The result (integer kcal) is saved to
`WorkoutProgress.total_calories` so it can be shown later without recalculating.
The old client-computed `total_calories` value is ignored.

- GYM: `apps/views/workouts.py` → `WorkoutCompleteView.post`
- HOME: `apps/views/home_workouts.py` → `HomeWorkoutCompleteView.post`
  (now also creates a `WorkoutProgress` COMPLETED record; before, home completions only
  touched `UserWorkoutProgress`, so home calories never reached stats/history).
- CUSTOM (favorites): `apps/views/favorite.py` → `CustomProgramCompleteView.post`, via
  `calories_for_custom_program`. A custom-program session is day one of
  `WorkoutCalculatorService.generate_program()` over the collection's favorited exercises,
  so it reuses the **GYM** formula with that day's sets/reps. Result saved to
  `CustomProgramProgress.total_calories`.

## Formulas
**GYM** (per exercise): `Exercise_Cal = (Exercise1repCal/100) * Exercise1repTime * Sets * Reps * (UserWeight/70)`
`Rest_Cal = WorkoutTimer(min) * 1.3 * 3.5 * UserWeight / 200`

**HOME** (per exercise, seconds throughout):
`Exercise_Cal = (Exercise1repCal/100/Exercise1repTime) * (UserWeight/70) * (Rounds * TimePer1ExerciseInRound)`
`ActiveTime(min) = (Rounds * TimePerRound) / 60`
`Rest_Cal = max(0, WorkoutTimer(min) - ActiveTime(min)) * 1.3 * 3.5 * UserWeight / 200`

`Total_Calories = Total_Exercise_Cal + Rest_Cal`, rounded to a whole number for display.

## Data model mapping (admin model unchanged)
| Spec input | Field |
|---|---|
| Exercise1repCal | `Exercise.calory` |
| Exercise1repTime (sec) | `Exercise.duration` |
| Sets / Reps (gym) | `WorkoutExercise.sets` / `.reps` |
| Rounds (home) | `Workout.rounds`, week-adjusted via `calculate_home_week_exercise` |
| TimePer1ExerciseInRound (sec) | `WorkoutExercise.minutes` (**stored as seconds** for home), week-adjusted |
| TimePerRound (sec) | Σ per-exercise round seconds (rest excluded) |
| UserWeight | `UserProfile.weight` |
| WorkoutTimer | `total_duration` POST field (seconds) |

> **Unit gotcha:** `WorkoutExercise.minutes` is labelled "Davomiyligi (minutda)" but holds
> **seconds** for HOME workouts — the live session player passes it to
> `calculate_home_week_exercise` as `base_duration_seconds`. The adapter follows the same
> convention, so no conversion is applied to the per-exercise time; only `TimePerRound` is
> divided by 60 for the minutes-based Rest_Cal subtraction.

## Edge cases
- Missing/0 `UserWeight` → 70 kg fallback, result flagged `is_estimated` (surfaced to the
  completion template as `workout_summary.calories_estimated`).
- HOME `Exercise1repTime = 0` → skip that exercise (avoids div-by-zero) + log a warning
  (`apps.calorie` logger); counted in `CalorieResult.skipped_exercises`.
- HOME negative rest → clamped to 0 (`Rest_Cal` is never negative).
- Timer always ceil'd to whole minutes (`54:13 → 55`).
- Final kcal rounded to an integer.

## Tests
`apps/tests/test_calorie_calculator.py` — 17 tests: hand-calculated 6-exercise GYM and a
HOME rounds workout, the seconds→minutes conversion in home Rest_Cal, the negative-rest
clamp, missing-weight fallback, timer round-up, div-by-zero skip+warning, plus DB-backed
adapter tests for the `Exercise.calory`/`.duration` field mapping (gym) and the
custom-program day-one GYM mapping.
