from django.db import migrations

CARDIO_MUSCLE_GROUP = "cardio"


def set_is_cardio_from_muscle_group(apps, schema_editor):
    Exercise = apps.get_model("apps", "Exercise")
    Exercise.objects.filter(primary_body_part=CARDIO_MUSCLE_GROUP).update(is_cardio=True)


def unset_is_cardio(apps, schema_editor):
    Exercise = apps.get_model("apps", "Exercise")
    Exercise.objects.filter(primary_body_part=CARDIO_MUSCLE_GROUP).update(is_cardio=False)


class Migration(migrations.Migration):

    dependencies = [
        ("apps", "0031_exercise_is_cardio"),
    ]

    operations = [
        migrations.RunPython(set_is_cardio_from_muscle_group, unset_is_cardio),
    ]
