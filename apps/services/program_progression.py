from apps.models import Program
from apps.services.programs import UserProgramService


PROFILE_GOAL_MAP = {
    "lose_weight": Program.Goal.FAT_LOSS,
    "gain_muscle": Program.Goal.MUSCLE_GAIN,
    "build_body": Program.Goal.RECOMPOSITION,
    "get_shape": Program.Goal.GENERAL,
}


def create_onboarding_program(profile):
    if profile.fitness_goal:
        profile.fitness_goal = PROFILE_GOAL_MAP.get(profile.fitness_goal, profile.fitness_goal)
    return UserProgramService.assign_auto_program_once(profile)
