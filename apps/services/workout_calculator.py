from dataclasses import dataclass


@dataclass
class WeekBlock:
    start_week: int
    end_week: int
    sets: int
    reps: int
    intensity: str


class WorkoutCalculatorService:
    """Builds a 6-week progressive workout schedule from favorite collection exercises."""

    DEFAULT_BLOCKS = (
        WeekBlock(1, 2, 3, 10, "light"),
        WeekBlock(3, 4, 4, 8, "medium"),
        WeekBlock(5, 6, 5, 6, "heavy"),
    )

    @classmethod
    def generate_program(cls, exercises, weeks=6, days_per_week=3):
        exercises = list(exercises)
        if not exercises:
            return []

        buckets = [[] for _ in range(days_per_week)]
        for idx, exercise in enumerate(exercises):
            buckets[idx % days_per_week].append(exercise)

        schedule = []
        for week_number in range(1, weeks + 1):
            block = cls._get_block_for_week(week_number)
            days = []
            for day_number in range(1, days_per_week + 1):
                days.append(
                    {
                        "day_number": day_number,
                        "sets": block.sets,
                        "reps": block.reps,
                        "intensity": block.intensity,
                        "exercises": [
                            {
                                "exercise_id": ex.id,
                                "name": ex.name,
                                "thumbnail": ex.thumbnail.url if ex.thumbnail else None,
                            }
                            for ex in buckets[day_number - 1]
                        ],
                    }
                )

            schedule.append(
                {
                    "week_number": week_number,
                    "days": days,
                }
            )

        return schedule

    @classmethod
    def _get_block_for_week(cls, week_number):
        for block in cls.DEFAULT_BLOCKS:
            if block.start_week <= week_number <= block.end_week:
                return block
        return cls.DEFAULT_BLOCKS[-1]
