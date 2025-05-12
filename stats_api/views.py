from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from django.db.models import Sum, Count, Q

from collections import Counter

from .models import Player, PlayerMatchStats

from .serializers import (
    PlayerSerializer,
    PlayerMatchStatsSerializer,
    PlayerOverallStatsSerializer,
)


def safe_division(numerator, denominator, default=0.0):
    if denominator is None or denominator == 0:
        return default
    try:
        result = numerator / denominator
        if result != result or result == float("inf") or result == float("-inf"):
            return default
        return result
    except (TypeError, ZeroDivisionError):
        return default

class PlayerViewSet(viewsets.ReadOnlyModelViewSet):
    """Эндпоинт API, который отображает всех пользователей."""
    queryset = Player.objects.all().order_by("username")
    serializer_class = PlayerSerializer
    lookup_field = "id"

    """Эндпоинт API для общей статистики игрока. Доступен по /api/players/{player_id}/overall_stats/"""
    @action(detail=True, methods=["get"], url_path="overall-stats")
    def overall_stats(self, request, id=None):
        player = self.get_object()
        player_stats_qs = PlayerMatchStats.objects.filter(player=player)

        total_matches = player_stats_qs.count()
        if total_matches == 0:
            return Response({
                "player_id": player.id,
                "username": player.username,
                "total_matches": 0,
                "total_wins": 0,
                "total_kills": 0,
                "total_deaths": 0,
                "total_assists": 0,
                "total_headshots": 0,
                "total_bodyshots": 0,
                "total_legshots": 0,
                "total_shots_fired": 0,
                "total_shots_hitted": 0,
                "total_skills_used": 0,
                "total_ultimates_used": 0,
                "kda_ratio": 0.0,
                "win_rate_overall": 0.0,
                "win_rate_last_20": 0.0,
                "headshot_percentage_overall": 0.0,
                "body_shot_percentage_overall": 0.0,
                "leg_shot_percentage_overall": 0.0,
                "headshot_percentage_of_hits": 0.0,
                "body_shot_percentage_of_hits": 0.0,
                "leg_shot_percentage_of_hits": 0.0,
                "average_kills_per_match": 0.0,
                "average_deaths_per_match": 0.0,
                "average_assists_per_match": 0.0,
                "average_skills_used_per_match": 0.0,
                "average_ultimates_used_per_match": 0.0,
                "average_time_alive_seconds": 0.0,
                "average_bomb_plants_per_match": 0.0,
                "average_bomb_defuses_per_match": 0.0,
                "average_armor1_purchases_per_match": 0.0,
                "average_armor2_purchases_per_match": 0.0,
                "favorite_weapon": None,
            }, status=status.HTTP_200_OK)

        aggregates = player_stats_qs.aggregate(
            total_wins=Count("pk", filter=Q(won_match=True)),
            total_kills=Sum("kills"),
            total_deaths=Sum("deaths"),
            total_assists=Sum("assists"),
            total_headshots=Sum("headshots"),
            total_bodyshots=Sum("bodyshots"),
            total_legshots=Sum("legshots"),
            total_shots_fired=Sum("total_shots_fired"),
            total_shots_hitted=Sum("total_shots_hitted"),
            total_skills_used=Sum("skills_used"),
            total_ultimates_used = Sum("ultimates_used"),
            total_time_alive_seconds=Sum("time_alive_seconds"),
            total_bomb_plants=Sum("bomb_plants"),
            total_bomb_defuses=Sum("bomb_defuses"),
            total_armor1_purchases=Sum("armor_lvl1_purchases"),
            total_armor2_purchases=Sum("armor_lvl2_purchases"),
        )

        total_wins = aggregates.get("total_wins") or 0
        total_kills = aggregates.get("total_kills") or 0
        total_deaths = aggregates.get("total_deaths") or 0
        total_assists = aggregates.get("total_assists") or 0
        total_headshots = aggregates.get("total_headshots") or 0
        total_bodyshots = aggregates.get("total_bodyshots") or 0
        total_legshots = aggregates.get("total_legshots") or 0
        total_shots_fired = aggregates.get("total_shots_fired") or 0
        total_shots_hitted = aggregates.get("total_shots_hitted") or 0
        total_skills_used = aggregates.get("total_skills_used") or 0
        total_ultimates_used = aggregates.get("total_ultimates_used") or 0
        total_time_alive_seconds = aggregates.get("total_time_alive_seconds") or 0
        total_bomb_plants = aggregates.get("total_bomb_plants") or 0
        total_bomb_defuses = aggregates.get("total_bomb_defuses") or 0
        total_armor1_purchases = aggregates.get("total_armor1_purchases") or 0
        total_armor2_purchases = aggregates.get("total_armor2_purchases") or 0

        # Расчет процента побед за последние 20 матчей
        last_20_matches = list(player_stats_qs[:20])
        count_last_20 = len(last_20_matches)
        wins_last_20 = sum(1 for stat in last_20_matches if stat.won_match)
        win_rate_last_20 = safe_division(wins_last_20 * 100.0, count_last_20)

        kda_ratio = safe_division(
            numerator=(total_kills + total_assists),
            denominator=total_deaths,
            default=(total_kills + total_assists)  # KDA по умолчанию, если смертей 0
        )

        win_rate_overall = safe_division(total_wins * 100.0, total_matches)

        headshot_percentage_overall = safe_division(total_headshots * 100.0, total_shots_fired)
        body_shot_percentage_overall = safe_division(total_bodyshots * 100.0, total_shots_fired)
        leg_shot_percentage_overall = safe_division(total_legshots * 100.0, total_shots_fired)
        headshot_percentage_of_hitted = safe_division(total_headshots * 100.0, total_shots_hitted)
        body_shot_percentage_of_hitted = safe_division(total_bodyshots * 100.0, total_shots_hitted)
        leg_shot_percentage_of_hitted = safe_division(total_legshots * 100.0, total_shots_hitted)

        average_kills = safe_division(total_kills, total_matches)
        average_deaths = safe_division(total_deaths, total_matches)
        average_assists = safe_division(total_assists, total_matches)
        average_skills_used = safe_division(total_skills_used, total_matches)
        average_ultimates_used = safe_division(total_ultimates_used, total_matches)
        average_time_alive = safe_division(total_time_alive_seconds, total_matches)
        average_bomb_plants = safe_division(total_bomb_plants, total_matches)
        average_bomb_defuses = safe_division(total_bomb_defuses, total_matches)
        average_armor1_purchases = safe_division(total_armor1_purchases, total_matches)
        average_armor2_purchases = safe_division(total_armor2_purchases, total_matches)

        # Определение любимого оружия
        weapon_counts = Counter(
            player_stats_qs.exclude(primary_weapon_used__isnull=True)
                           .exclude(primary_weapon_used__exact="")
                           .values_list("primary_weapon_used", flat=True)
        )
        favorite_weapon = weapon_counts.most_common(1)[0][0] if weapon_counts else None

        # Формирование данных для сериализатора
        stats_data = {
            "player_id": player.id,
            "username": player.username,
            "total_matches": total_matches,
            "total_wins": total_wins,
            "total_kills": total_kills,
            "total_deaths": total_deaths,
            "total_assists": total_assists,
            "total_headshots": total_headshots,
            "total_bodyshots": total_bodyshots,
            "total_legshots": total_legshots,
            "total_shots_fired": total_shots_fired,
            "total_shots_hitted": total_shots_hitted,
            "total_skills_used": total_skills_used,
            "total_ultimates_used": total_ultimates_used,

            "kda_ratio": round(kda_ratio, 2),
            "win_rate_overall": round(win_rate_overall, 1),
            "win_rate_last_20": round(win_rate_last_20, 1),
            "headshot_percentage_overall": round(headshot_percentage_overall, 1),
            "body_shot_percentage_overall": round(body_shot_percentage_overall, 1),
            "leg_shot_percentage_overall": round(leg_shot_percentage_overall, 1),
            "headshot_percentage_of_hits": round(headshot_percentage_of_hitted, 1),
            "body_shot_percentage_of_hits": round(body_shot_percentage_of_hitted, 1),
            "leg_shot_percentage_of_hits": round(leg_shot_percentage_of_hitted, 1),

            "average_kills_per_match": round(average_kills, 2),
            "average_deaths_per_match": round(average_deaths, 2),
            "average_assists_per_match": round(average_assists, 2),
            "average_skills_used_per_match": round(average_skills_used, 2),
            "average_ultimates_used_per_match": round(average_ultimates_used, 2),
            "average_time_alive_seconds": round(average_time_alive, 1),
            "average_bomb_plants_per_match": round(average_bomb_plants, 2),
            "average_bomb_defuses_per_match": round(average_bomb_defuses, 2),
            "average_armor1_purchases_per_match": round(average_armor1_purchases, 2),
            "average_armor2_purchases_per_match": round(average_armor2_purchases, 2),

            "favorite_weapon": favorite_weapon,
        }

        # Сериализуем подготовленные данные
        serializer = PlayerOverallStatsSerializer(data=stats_data)
        serializer.is_valid(raise_exception=True) # Проверяем, что данные соответствуют формату сериализатора
        return Response(serializer.validated_data)

    # Эндпоинт для истории матчей игрока. Доступен по /api/players/{player_id}/match-history/
    @action(detail=True, methods=["get"], url_path="match-history")
    def match_history(self, request, id=None):
        player = self.get_object()

        # Оптимизация запроса (подгружаем данные матча сразу)
        queryset = PlayerMatchStats.objects.filter(player=player).select_related("match")

        # Пагинация
        page = self.paginate_queryset(queryset)
        if page is not None:
            # Используем сериализатор для отдельных записей статистики
            serializer = PlayerMatchStatsSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)

        # Если пагинация не используется, возвращаем весь список
        serializer = PlayerMatchStatsSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)
