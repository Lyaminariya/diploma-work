# Generated by Django 5.2 on 2025-05-01 17:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stats_api', '0003_rename_total_shots_hit_playermatchstats_total_shots_hitted'),
    ]

    operations = [
        migrations.RenameField(
            model_name='match',
            old_name='duration_secons',
            new_name='duration_seconds',
        ),
    ]
