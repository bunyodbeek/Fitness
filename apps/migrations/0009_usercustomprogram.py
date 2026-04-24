from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("apps", "0008_remove_progressionsetting_multiplier_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserCustomProgram",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100)),
                ("goal", models.CharField(choices=[("mg", "Muscle Gain"), ("ft", "Fat Loss"), ("rc", "Recovery")], max_length=10)),
                ("weeks", models.IntegerField(default=6)),
                ("is_active", models.BooleanField(default=True)),
                ("collection", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="apps.favoritecollection")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="custom_programs", to="apps.userprofile")),
            ],
            options={
                "verbose_name": "Custom Program",
                "verbose_name_plural": "Custom Programs",
                "ordering": ["-created_at"],
            },
        ),
    ]
