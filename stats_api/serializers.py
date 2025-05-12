from rest_framework import serializers
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import Player, Match, PlayerMatchStats


class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ["id", "username", "created_at"]

class MatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Match
        fields = ["id", "game_match_id", "match_timestamp", "duration_seconds"]


class PlayerMatchStatsSerializer(serializers.ModelSerializer):
    player_username = serializers.CharField(source="player.username", read_only=True)
    match_info = MatchSerializer(source="match", read_only=True)

    class Meta:
        model = PlayerMatchStats
        fields = [
            "id", "player", "player_username", "match", "match_info", "won_match", "kills", "deaths", "assists", "kda",
            "skills_used", "ultimates_used", "time_alive_seconds", "bomb_plants", "bomb_defuses", "headshots",
            "bodyshots", "legshots", "total_shots_fired", "total_shots_hitted", "headshot_rate", "primary_weapon_used",
            "armor_lvl1_purchases", "armor_lvl2_purchases"
        ]
        read_only_fields = ["player", "match"]


class PlayerOverallStatsSerializer(serializers.Serializer):
    player_id = serializers.IntegerField()
    username = serializers.CharField()
    total_matches = serializers.IntegerField()
    total_wins = serializers.IntegerField()
    total_kills = serializers.IntegerField()
    total_deaths = serializers.IntegerField()
    total_assists = serializers.IntegerField()
    total_headshots = serializers.IntegerField()
    total_bodyshots = serializers.IntegerField()
    total_legshots = serializers.IntegerField()
    total_shots_fired = serializers.IntegerField()
    total_shots_hitted = serializers.IntegerField()
    total_skills_used =serializers.IntegerField()
    total_ultimates_used = serializers.IntegerField()

    kda_ratio = serializers.FloatField()

    win_rate_overall = serializers.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    win_rate_last_20 = serializers.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])

    headshot_percentage_overall = serializers.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
                                                         help_text="Процент попаданий в голову от всех выстрелов")
    body_shot_percentage_overall = serializers.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
                                                          help_text="Процент попаданий в тело от всех выстрелов")
    leg_shot_percentage_overall = serializers.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
                                                         help_text="Процент попаданий в ноги от всех выстрелов")
    headshot_percentage_of_hits = serializers.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
                                                         help_text="Процент попаданий в голову от попавших выстрелов")
    body_shot_percentage_of_hits = serializers.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
                                                          help_text="Процент попаданий в тело от попавших выстрелов")
    leg_shot_percentage_of_hits = serializers.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
                                                         help_text="Процент попаданий в ноги от попавших выстрелов")

    average_kills_per_match = serializers.FloatField()
    average_deaths_per_match = serializers.FloatField()
    average_assists_per_match = serializers.FloatField()
    average_skills_used_per_match = serializers.FloatField()
    average_ultimates_used_per_match = serializers.FloatField()
    average_time_alive_seconds = serializers.FloatField()
    average_bomb_plants_per_match = serializers.FloatField()
    average_bomb_defuses_per_match = serializers.FloatField()
    average_armor1_purchases_per_match = serializers.FloatField()
    average_armor2_purchases_per_match = serializers.FloatField()

    favorite_weapon = serializers.CharField(allow_null=True, allow_blank=True)
