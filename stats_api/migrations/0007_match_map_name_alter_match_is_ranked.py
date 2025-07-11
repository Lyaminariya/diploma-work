# Generated by Django 5.2 on 2025-05-04 18:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stats_api', '0006_alter_player_options_remove_match_map_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='match',
            name='map_name',
            field=models.CharField(blank=True, help_text='Название карты', max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='match',
            name='is_ranked',
            field=models.BooleanField(blank=True, help_text='Является ли матч ранговым', null=True),
        ),
    ]
