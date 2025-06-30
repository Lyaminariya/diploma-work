from rest_framework import serializers
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import Player, Match, PlayerMatchStats, GameNames


class PlayerSerializer(serializers.ModelSerializer):
    game_name_display = serializers.CharField(source='get_game_name_display', read_only=True)

    class Meta:
        model = Player
        fields = ["id", "username", "puuid", "game_name", "game_name_display", "created_at", "rank"]


class MatchSerializer(serializers.ModelSerializer):
    game_name_display = serializers.CharField(source='get_game_name_display', read_only=True)

    class Meta:
        model = Match
        fields = [
            "id", "game_match_id", "game_name", "game_name_display", "match_timestamp",
            "duration_seconds", "map_name", "game_mode", "is_ranked"
        ]


class PlayerMatchStatsSerializer(serializers.ModelSerializer):
    player_username = serializers.CharField(source="player.username", read_only=True)
    game_name_display = serializers.CharField(source='get_game_name_display',
                                              read_only=True)
    match_info = MatchSerializer(source="match", read_only=True)

    class Meta:
        model = PlayerMatchStats
        fields = [
            "id", "player", "player_username", "match", "match_info", "game_name", "game_name_display",
            "won_match", "kills", "deaths", "assists", "kda", "headshot_rate", "damage_dealt",
            # Valorant
            "skills_used", "ultimates_used", "bomb_plants", "bomb_defuses",
            "headshots", "bodyshots", "legshots", "total_shots_fired", "total_shots_hitted",
            "primary_weapon_used", "armor_lvl1_purchases", "armor_lvl2_purchases",
            # PUBG
            "boosts_used", "heals_used", "revives", "dbnos", "longest_kill_distance",
            # Общее
            "time_alive_seconds",
        ]
        read_only_fields = ["player", "match"]


class PlayerOverallStatsSerializer(serializers.Serializer):
    player_id = serializers.IntegerField()
    username = serializers.CharField()
    game_name = serializers.ChoiceField(choices=GameNames.choices)

    total_matches = serializers.IntegerField()
    total_wins = serializers.IntegerField()
    total_kills = serializers.IntegerField()
    total_deaths = serializers.IntegerField()
    total_assists = serializers.IntegerField()

    # Valorant поля
    total_valorant_headshots = serializers.IntegerField(required=False, allow_null=True)
    total_bodyshots = serializers.IntegerField(required=False, allow_null=True)
    total_legshots = serializers.IntegerField(required=False, allow_null=True)
    total_shots_fired = serializers.IntegerField(required=False, allow_null=True)
    total_shots_hitted = serializers.IntegerField(required=False, allow_null=True)
    total_skills_used = serializers.IntegerField(required=False, allow_null=True)
    total_ultimates_used = serializers.IntegerField(required=False, allow_null=True)

    # PUBG поля
    total_pubg_headshot_kills = serializers.IntegerField(required=False,
                                                         allow_null=True)
    total_damage_dealt = serializers.FloatField(required=False, allow_null=True)
    total_boosts_used = serializers.IntegerField(required=False, allow_null=True)
    total_heals_used = serializers.IntegerField(required=False, allow_null=True)
    total_revives = serializers.IntegerField(required=False, allow_null=True)
    total_dbnos = serializers.IntegerField(required=False, allow_null=True)

    kda_ratio = serializers.FloatField()
    win_rate_overall = serializers.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    win_rate_last_20 = serializers.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
                                              required=False)

    # Valorant проценты
    headshot_percentage_overall_valorant = serializers.FloatField(required=False, allow_null=True)
    headshot_percentage_of_hits_valorant = serializers.FloatField(required=False, allow_null=True)

    # PUBG среднее
    average_headshot_rate_pubg = serializers.FloatField(required=False, allow_null=True)

    average_kills_per_match = serializers.FloatField()
    average_deaths_per_match = serializers.FloatField()
    average_assists_per_match = serializers.FloatField()

    # Valorant среднее
    average_skills_used_per_match = serializers.FloatField(required=False, allow_null=True)

    # PUBG среднее
    average_damage_dealt_per_match = serializers.FloatField(required=False, allow_null=True)
    average_boosts_used_per_match = serializers.FloatField(required=False, allow_null=True)
    average_heals_used_per_match = serializers.FloatField(required=False, allow_null=True)

    favorite_weapon = serializers.CharField(allow_null=True, required=False)  # Преимущественно Valorant

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        game_name_value = instance.get('game_name')
        if game_name_value:
            try:
                representation['game_name_display'] = GameNames(game_name_value).label
            except ValueError:  # На случай если game_name_value невалиден
                representation['game_name_display'] = game_name_value
        return representation


class DBSCANResultItemSerializer(serializers.Serializer):
    player_id = serializers.IntegerField()
    puuid = serializers.CharField(required=False, allow_null=True)
    username = serializers.CharField()
    game_name = serializers.ChoiceField(choices=GameNames.choices)
    cluster = serializers.IntegerField()

    # Общие метрики
    avg_kills = serializers.FloatField()
    avg_deaths = serializers.FloatField()
    avg_assists = serializers.FloatField()
    avg_kda = serializers.FloatField()
    avg_headshot_rate = serializers.FloatField()
    avg_damage_dealt = serializers.FloatField()
    avg_unique_game_abilities = serializers.FloatField()


class DBSCANResultSerializer(serializers.Serializer):
    player_id = serializers.IntegerField()
    puuid = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    username = serializers.CharField()
    game_name = serializers.CharField()
    cluster = serializers.IntegerField()
    num_matches = serializers.IntegerField(required=False, allow_null=True)
    avg_kills = serializers.FloatField(required=False, allow_null=True)
    avg_deaths = serializers.FloatField(required=False, allow_null=True)
    avg_assists = serializers.FloatField(required=False, allow_null=True)
    avg_kda = serializers.FloatField(required=False, allow_null=True)
    avg_headshot_rate = serializers.FloatField(required=False, allow_null=True)
    avg_damage_dealt = serializers.FloatField(required=False, allow_null=True)
    avg_unique_game_abilities = serializers.FloatField(required=False, allow_null=True)
    combat_performance_score = serializers.FloatField(required=False, allow_null=True)
