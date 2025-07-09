from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.parsers import MultiPartParser, FormParser
import django_filters.rest_framework

from django.db import transaction, IntegrityError
from django.db.models import Sum, Count, Q, Avg, F, Value, FloatField, CharField, Field, Case, When, IntegerField, Min, Max
from django.db.models.functions import Coalesce, Cast
from django.utils.dateparse import parse_datetime

import csv
import io
import numpy as np
import pandas as pd
from collections import defaultdict
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN

import logging

from .models import Player, PlayerMatchStats, GameNames, Match
from .serializers import (
    PlayerSerializer,
    MatchSerializer,
    PlayerMatchStatsSerializer,
    DBSCANResultSerializer,
)

logger_views = logging.getLogger(__name__)


# Вспомогательные функции
def safe_division_scalar(numerator, denominator, default=0.0):
    if numerator is None or denominator is None or pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return default
    try:
        result = numerator / denominator
        if pd.isna(result) or result == float("inf") or result == float("-inf"):
            return default
        return result
    except (TypeError, ZeroDivisionError):
        return default


def safe_division_series(numerator_series, denominator_series, default=0.0):
    num_is_series = isinstance(numerator_series, pd.Series)
    den_is_series = isinstance(denominator_series, pd.Series)

    if not num_is_series and not den_is_series:
        return safe_division_scalar(numerator_series, denominator_series, default)

    if not num_is_series:
        numerator_series = pd.Series(numerator_series, index=denominator_series.index if den_is_series else None)
    if not den_is_series:
        denominator_series = pd.Series(denominator_series, index=numerator_series.index if num_is_series else None)

    if num_is_series and den_is_series and not numerator_series.index.equals(denominator_series.index):
        logger_views.warning("Series for safe_division have mismatched indexes. Attempting to align if lengths match.")
        if len(numerator_series) == len(denominator_series):
            try:
                denominator_series = denominator_series.reindex(numerator_series.index)
            except Exception as e:
                logger_views.error(f"Failed to reindex series in safe_division: {e}")
                return pd.Series(default, index=numerator_series.index, dtype=float)
        else:
            return pd.Series(default, index=numerator_series.index, dtype=float)

    result_series = pd.Series(default, index=numerator_series.index, dtype=float)
    safe_condition = (denominator_series != 0) & (~pd.isna(denominator_series)) & (~pd.isna(numerator_series))

    if safe_condition.any():
        safe_num = numerator_series[safe_condition].astype(float)
        safe_den = denominator_series[safe_condition].astype(float)
        result_series.loc[safe_condition] = safe_num / safe_den

    result_series.replace([np.inf, -np.inf], default, inplace=True)
    result_series.fillna(default, inplace=True)
    return result_series


class PlayerFilter(django_filters.FilterSet):
    game_name = django_filters.CharFilter(lookup_expr='iexact')

    class Meta:
        model = Player
        fields = ['game_name']


class MatchFilter(django_filters.FilterSet):
    game_name = django_filters.CharFilter(lookup_expr='iexact')
    is_ranked = django_filters.BooleanFilter()
    map_name = django_filters.CharFilter(lookup_expr='icontains')
    game_mode = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Match
        fields = ['game_name', 'is_ranked', 'map_name', 'game_mode']


class PlayerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Player.objects.all().order_by("username", "game_name")
    serializer_class = PlayerSerializer
    pagination_class = LimitOffsetPagination
    filter_backends = [django_filters.rest_framework.DjangoFilterBackend]
    filterset_class = PlayerFilter

    @action(detail=False, methods=['get'], url_path='by_puuid')
    def by_puuid(self, request):
        puuid = request.query_params.get('puuid')
        game_name = request.query_params.get('game_name', '').strip().lower()
        if not puuid or not game_name:
            return Response({'error': 'Параметры puuid и game_name обязательны.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            player = Player.objects.get(puuid__iexact=puuid, game_name=game_name)
            serializer = self.get_serializer(player)
            return Response(serializer.data)
        except Player.DoesNotExist:
            return Response({'detail': f'Игрок с PUUID {puuid} для игры {game_name} не найден.'},
                            status=status.HTTP_404_NOT_FOUND)
        except Player.MultipleObjectsReturned:
            logger_views.error(f"Найдено несколько игроков для puuid {puuid} и игры {game_name}")
            return Response({'detail': 'Найдено несколько игроков. Проблема целостности данных.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='by_username')
    def by_username(self, request):
        username = request.query_params.get('username')
        game_name = request.query_params.get('game_name', '').strip().lower()
        if not username or not game_name:
            return Response({'error': 'Параметры username и game_name обязательны.'},
                            status=status.HTTP_400_BAD_REQUEST)

        players = Player.objects.filter(username__iexact=username, game_name=game_name)
        if not players.exists():
            return Response({'detail': f'Игрок с Username {username} для игры {game_name} не найден.'},
                            status=status.HTTP_404_NOT_FOUND)

        if players.count() > 1:
            logger_views.warning(
                f"Найдено несколько игроков для username '{username}' и игры {game_name}. Возвращаем первого.")

        player = players.first()
        serializer = self.get_serializer(player)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="match-history")
    def match_history(self, request):
        player_puuid = request.query_params.get('player_puuid')
        game_name = request.query_params.get('game_name', '').strip().lower()
        if not player_puuid or not game_name:
            return Response({'error': "Параметры 'player_puuid' и 'game_name' обязательны."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            player = Player.objects.get(puuid__iexact=player_puuid, game_name=game_name)
        except Player.DoesNotExist:
            return Response({'detail': f'Игрок с PUUID {player_puuid} и игрой {game_name} не найден.'},
                            status=status.HTTP_404_NOT_FOUND)

        queryset = PlayerMatchStats.objects.filter(player=player).select_related("match", "player").order_by(
            '-match__match_timestamp')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = PlayerMatchStatsSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)

        serializer = PlayerMatchStatsSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)


class MatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Match.objects.all().order_by('-match_timestamp')
    serializer_class = MatchSerializer
    pagination_class = LimitOffsetPagination
    filter_backends = [django_filters.rest_framework.DjangoFilterBackend]
    filterset_class = MatchFilter

    @action(detail=False, methods=['get'], url_path='by_game_match_id')
    def by_game_match_id(self, request):
        game_match_id = request.query_params.get('game_match_id')
        game_name = request.query_params.get('game_name', '').strip().lower()
        if not game_match_id or not game_name:
            return Response({'error': 'Параметры game_match_id и game_name обязательны.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            match = Match.objects.get(game_match_id__iexact=game_match_id, game_name=game_name)
            serializer = self.get_serializer(match)
            return Response(serializer.data)
        except Match.DoesNotExist:
            return Response({'detail': f'Матч с ID {game_match_id} для игры {game_name} не найден.'},
                            status=status.HTTP_404_NOT_FOUND)
        except Match.MultipleObjectsReturned:
            logger_views.error(f"Найдено несколько матчей для game_match_id {game_match_id} и игры {game_name}")
            return Response({'detail': 'Найдено несколько матчей. Проблема целостности данных.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PlayerMatchStatsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PlayerMatchStats.objects.select_related('player', 'match').all()
    serializer_class = PlayerMatchStatsSerializer

    @action(detail=False, methods=['get'], url_path='by_identifiers')
    def by_identifiers(self, request):
        player_puuid = request.query_params.get('player_puuid')
        game_match_id = request.query_params.get('game_match_id')
        game_name = request.query_params.get('game_name', '').strip().lower()

        if not player_puuid or not game_match_id or not game_name:
            return Response({'error': 'Параметры player_puuid, game_match_id и game_name обязательны.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            player = Player.objects.get(puuid__iexact=player_puuid, game_name=game_name)
        except Player.DoesNotExist:
            return Response({'detail': f'Игрок с PUUID {player_puuid} (игра: {game_name}) не найден.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            match = Match.objects.get(game_match_id__iexact=game_match_id, game_name=game_name)
        except Match.DoesNotExist:
            return Response({'detail': f'Матч с ID {game_match_id} (игра: {game_name}) не найден.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            stat_entry = PlayerMatchStats.objects.get(player_id=player.id, match_id=match.id)
            serializer = self.get_serializer(stat_entry)
            return Response(serializer.data)
        except PlayerMatchStats.DoesNotExist:
            return Response({'detail': 'Статистика для данного игрока и матча не найдена.'},
                            status=status.HTTP_404_NOT_FOUND)
        except PlayerMatchStats.MultipleObjectsReturned:
            logger_views.error(f"Найдено несколько записей статистики для player_id {player.id} и match_id {match.id}")
            return Response({'detail': 'Найдено несколько записей статистики. Проблема целостности данных.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CSVImportView(views.APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        players_file = request.FILES.get('players_csv')
        matches_file = request.FILES.get('matches_csv')
        stats_file = request.FILES.get('stats_csv')
        game_name_from_form = request.data.get('game_name')

        if not game_name_from_form or not game_name_from_form.strip():
            return Response(
                {"error": "Параметр 'game_name' (название игры) обязателен и не может быть пустым."},
                status=status.HTTP_400_BAD_REQUEST
            )

        game_name = game_name_from_form.strip().lower()

        if not players_file and not matches_file and not stats_file:
            return Response({"error": "Необходимо загрузить хотя бы один CSV файл."},
                            status=status.HTTP_400_BAD_REQUEST)

        results = {"message": "Обработка файлов начата.", "details": {}, "row_errors": {}}

        try:
            with transaction.atomic():
                if players_file:
                    details, file_row_errors = self._import_players(players_file, game_name)
                    results["details"]["players_csv"] = details
                    if file_row_errors: results["row_errors"]["players_csv"] = file_row_errors

                if matches_file:
                    details, file_row_errors = self._import_matches(matches_file, game_name)
                    results["details"]["matches_csv"] = details
                    if file_row_errors: results["row_errors"]["matches_csv"] = file_row_errors

                if stats_file:
                    details, file_row_errors = self._import_stats(stats_file, game_name)
                    results["details"]["stats_csv"] = details
                    if file_row_errors: results["row_errors"]["stats_csv"] = file_row_errors

            has_row_errors = any(bool(errors_list) for errors_list in results["row_errors"].values() if errors_list)

            if has_row_errors:
                results[
                    "message"] = "Файлы обработаны, но в некоторых строках обнаружены ошибки. См. 'row_errors' для деталей."
                return Response(results, status=status.HTTP_207_MULTI_STATUS)

            results["message"] = "Все предоставленные файлы успешно импортированы."
            return Response(results, status=status.HTTP_201_CREATED)

        except IntegrityError as e:
            logger_views.error(f"Ошибка целостности при импорте CSV для игры '{game_name}': {e}")
            return Response({"error": f"Ошибка целостности данных: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger_views.error(f"Непредвиденная ошибка при импорте CSV для игры '{game_name}': {e}", exc_info=True)
            return Response({"error": f"Произошла непредвиденная ошибка: {e}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _parse_csv(self, file_obj):
        try:
            decoded_file = file_obj.read().decode('utf-8-sig')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            return list(reader)
        except UnicodeDecodeError:
            file_obj.seek(0)
            try:
                decoded_file = file_obj.read().decode('cp1251')
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)
                return list(reader)
            except Exception as e_cp1251:
                raise ValueError(f"Не удалось декодировать файл (пробовались UTF-8, CP1251). Ошибка: {e_cp1251}")
        except Exception as e:
            raise ValueError(f"Ошибка при чтении CSV: {e}")

    def _convert_to_int_or_default(self, value_str, default=0):
        # если default=none, то при пустой строке или ошибке вернет none
        if value_str is None or str(value_str).strip() == '':
            return default
        try:
            return int(float(str(value_str).strip()))
        except (ValueError, TypeError):
            return default

    def _convert_to_float_or_default(self, value_str, default=0.0):
        if value_str is None or str(value_str).strip() == '':
            return default
        try:
            return float(str(value_str).strip())
        except (ValueError, TypeError):
            return default

    def _import_players(self, file_obj, game_name):
        created_count, updated_count, skipped_count = 0, 0, 0
        row_errors = []
        try:
            data = self._parse_csv(file_obj)
        except ValueError as e:
            return {"error": str(e)}, [{"row_number": "N/A", "errors": str(e)}]

        for i, row in enumerate(data):
            row_num = i + 2
            try:
                puuid = row.get('puuid', '').strip()
                if not puuid:
                    row_errors.append({"row_number": row_num, "errors": "Отсутствует 'puuid'", "data": row})
                    skipped_count += 1
                    continue

                player_defaults = {
                    'username': row.get('username', '').strip() or None,
                    'rank': row.get('rank', '').strip() or None
                }
                player_defaults_cleaned = {k: v for k, v in player_defaults.items() if v is not None}

                player, created = Player.objects.update_or_create(
                    puuid=puuid,
                    game_name=game_name,
                    defaults=player_defaults_cleaned
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                row_errors.append({"row_number": row_num, "errors": str(e), "data": row})
                skipped_count += 1
        return {"created": created_count, "updated": updated_count, "skipped": skipped_count}, row_errors

    def _import_matches(self, file_obj, game_name):
        created_count, updated_count, skipped_count = 0, 0, 0
        row_errors = []
        try:
            data = self._parse_csv(file_obj)
        except ValueError as e:
            return {"error": str(e)}, [{"row_number": "N/A", "errors": str(e)}]

        for i, row in enumerate(data):
            row_num = i + 2
            try:
                game_match_id = row.get('game_match_id', '').strip()
                if not game_match_id:
                    row_errors.append({"row_number": row_num, "errors": "Отсутствует 'game_match_id'", "data": row})
                    skipped_count += 1
                    continue

                timestamp_str = row.get('match_timestamp', '').strip()
                dt_obj = None
                if timestamp_str:
                    dt_obj = parse_datetime(timestamp_str)
                    if not dt_obj:
                        row_errors.append(
                            {"row_number": row_num, "errors": f"Неверный формат match_timestamp: {timestamp_str}",
                             "data": row})
                        skipped_count += 1
                        continue

                match_defaults = {
                    'match_timestamp': dt_obj,
                    'duration_seconds': self._convert_to_int_or_default(row.get('duration_seconds'), None),
                    'map_name': row.get('map_name', '').strip() or None,
                    'game_mode': row.get('game_mode', '').strip() or None,
                    'is_ranked': str(row.get('is_ranked', '')).lower() in ['true', '1', 'yes'] if row.get('is_ranked',
                                                                                                          '').strip() else None,
                    'rounds_played': self._convert_to_int_or_default(row.get('rounds_played'), None),
                }
                match_defaults_cleaned = {k: v for k, v in match_defaults.items() if
                                          v is not None or k == 'is_ranked'}

                match, created = Match.objects.update_or_create(
                    game_match_id=game_match_id,
                    game_name=game_name,
                    defaults=match_defaults_cleaned
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                row_errors.append({"row_number": row_num, "errors": str(e), "data": row})
                skipped_count += 1
        return {"created": created_count, "updated": updated_count, "skipped": skipped_count}, row_errors

    def _import_stats(self, file_obj, game_name_context):
        created_count, updated_count, skipped_count = 0, 0, 0
        row_errors = []
        try:
            data = self._parse_csv(file_obj)
        except ValueError as e:
            return {"error": str(e)}, [{"row_number": "N/A", "errors": str(e)}]

        for i, row in enumerate(data):
            row_num = i + 2
            try:
                player_puuid = row.get('player_puuid', '').strip()
                match_game_id = row.get('match_game_id', '').strip()
                if not player_puuid or not match_game_id:
                    row_errors.append(
                        {"row_number": row_num, "errors": "Отсутствуют 'player_puuid' или 'match_game_id'",
                         "data": row})
                    skipped_count += 1
                    continue

                try:
                    player = Player.objects.get(puuid=player_puuid, game_name=game_name_context)
                    match = Match.objects.get(game_match_id=match_game_id, game_name=game_name_context)
                except Player.DoesNotExist:
                    row_errors.append({"row_number": row_num,
                                       "errors": f"Игрок PUUID {player_puuid} ({game_name_context}) не найден.",
                                       "data": row})
                    skipped_count += 1
                    continue
                except Match.DoesNotExist:
                    row_errors.append(
                        {"row_number": row_num, "errors": f"Матч ID {match_game_id} ({game_name_context}) не найден.",
                         "data": row})
                    skipped_count += 1
                    continue

                stats_defaults = {
                    'game_name': game_name_context,
                    'won_match': str(row.get('won_match', 'false')).lower() in ['true', '1', 'yes'],
                    'kills': self._convert_to_int_or_default(row.get('kills')),
                    'deaths': self._convert_to_int_or_default(row.get('deaths')),
                    'assists': self._convert_to_int_or_default(row.get('assists')),
                    'kda': self._convert_to_float_or_default(row.get('kda')),
                    'headshot_rate': self._convert_to_float_or_default(row.get('headshot_rate'), None),
                    'damage_dealt': self._convert_to_int_or_default(row.get('damage_dealt')),
                    'time_alive_seconds': self._convert_to_int_or_default(row.get('time_alive_seconds'), None),

                    # Valorant поля
                    'skills_used': self._convert_to_int_or_default(row.get('skills_used'), None),
                    'ultimates_used': self._convert_to_int_or_default(row.get('ultimates_used'), None),
                    'bomb_plants': self._convert_to_int_or_default(row.get('bomb_plants'), None),
                    'bomb_defuses': self._convert_to_int_or_default(row.get('bomb_defuses'), None),
                    'headshots': self._convert_to_int_or_default(row.get('headshots'), None),
                    'bodyshots': self._convert_to_int_or_default(row.get('bodyshots'), None),
                    'legshots': self._convert_to_int_or_default(row.get('legshots'), None),
                    'total_shots_hitted': self._convert_to_int_or_default(row.get('total_shots_hitted'), None),
                    'total_shots_fired': self._convert_to_int_or_default(row.get('total_shots_fired'), None),
                    'primary_weapon_used': row.get('primary_weapon_used', '').strip() or None,
                    'armor_lvl1_purchases': self._convert_to_int_or_default(row.get('armor_lvl1_purchases'), None),
                    'armor_lvl2_purchases': self._convert_to_int_or_default(row.get('armor_lvl2_purchases'), None),

                    # PUBG поля
                    'boosts_used': self._convert_to_int_or_default(row.get('boosts_used'), None),
                    'heals_used': self._convert_to_int_or_default(row.get('heals_used'), None),
                    'revives': self._convert_to_int_or_default(row.get('revives'), None),
                    'dbnos': self._convert_to_int_or_default(row.get('dbnos'), None),
                    'longest_kill_distance': self._convert_to_int_or_default(row.get('longest_kill_distance'), None),

                    # общие поля
                    'unique_abilities_used': self._convert_to_int_or_default(row.get('unique_abilities_used'), None),
                }
                stats_defaults_cleaned = {k: v for k, v in stats_defaults.items() if
                                          v is not None or k == 'won_match'}

                stat, created = PlayerMatchStats.objects.update_or_create(
                    player=player,
                    match=match,
                    defaults=stats_defaults_cleaned
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                logger_views.error(f"Error processing row {row_num} for stats: {e}, data: {row}")
                row_errors.append({"row_number": row_num, "errors": str(e), "data": row})
                skipped_count += 1
        return {"created": created_count, "updated": updated_count, "skipped": skipped_count}, row_errors


class AvailableGamesView(views.APIView):
    def get(self, request, *args, **kwargs):
        player_games = Player.objects.values_list('game_name', flat=True).distinct()
        match_games = Match.objects.values_list('game_name', flat=True).distinct()
        stats_games = PlayerMatchStats.objects.values_list('game_name', flat=True).distinct()

        all_games_set = set()
        all_games_set.update(g.lower() for g in player_games if g)
        all_games_set.update(g.lower() for g in match_games if g)
        all_games_set.update(g.lower() for g in stats_games if g)

        for value, _ in GameNames.choices:
            all_games_set.add(value.lower())

        game_options = []
        for game_value in sorted(list(all_games_set)):
            label = game_value
            try:
                found_choice = next((lbl for val_choice, lbl in GameNames.choices if val_choice.lower() == game_value),
                                    None)
                if found_choice:
                    label = found_choice
                else:
                    label = game_value.capitalize() if game_value else "Unknown"
            except ValueError:
                label = game_value.capitalize() if game_value else "Unknown"
            if game_value:
                game_options.append({'value': game_value, 'label': label})

        return Response(game_options)


class DBSCANAnalysisView(views.APIView):
    permission_classes = []

    def get(self, request, *args, **kwargs):
        game_name_query = request.query_params.get('game_name', '').strip().lower()
        if not game_name_query:
            return Response(
                {"error": "Параметр 'game_name' обязателен."},
                status=status.HTTP_400_BAD_REQUEST)
        game_name = game_name_query

        try:
            eps = float(request.query_params.get('eps', 0.3))
            min_samples = int(request.query_params.get('min_samples', 4))
            min_matches_for_analysis = int(request.query_params.get('min_matches', 5))
        except ValueError:
            return Response(
                {"error": "Параметры 'eps', 'min_samples', 'min_matches' должны быть числами."},
                status=status.HTTP_400_BAD_REQUEST)

        output_float = FloatField()
        aggregates_for_features = {
            'avg_kills': Avg(Coalesce(F('kills'), Value(0)), output_field=output_float),
            'avg_deaths': Avg(Coalesce(F('deaths'), Value(0)), output_field=output_float),
            'avg_assists': Avg(Coalesce(F('assists'), Value(0)), output_field=output_float),
            'avg_kda': Avg(Coalesce(F('kda'), Value(0.0)), output_field=output_float),
            'avg_headshot_rate': Avg(Coalesce(F('headshot_rate'), Value(0.0)), output_field=output_float),
            'avg_damage_dealt': Avg(Coalesce(F('damage_dealt'), Value(0.0)), output_field=output_float),
            'num_matches': Count('id')
        }

        has_direct_unique_field = False
        try:
            PlayerMatchStats._meta.get_field('unique_abilities_used')
            has_direct_unique_field = True
            aggregates_for_features['avg_direct_unique_abilities'] = Avg(Coalesce(F('unique_abilities_used'), Value(0)),
                                                                         output_field=output_float)
        except Field.DoesNotExist:
            pass
        except AttributeError:
            pass

        try:
            game_enum_value = GameNames(game_name).value
            if game_enum_value == GameNames.VALORANT.value:
                aggregates_for_features.update({
                    'sum_skills_used': Sum(Coalesce(F('skills_used'), Value(0))),
                    'sum_ultimates_used': Sum(Coalesce(F('ultimates_used'), Value(0))),
                })
            elif game_enum_value == GameNames.PUBG.value:
                aggregates_for_features.update({
                    'sum_heals_used': Sum(Coalesce(F('heals_used'), Value(0))),
                    'sum_boosts_used': Sum(Coalesce(F('boosts_used'), Value(0))),
                })
        except ValueError:
            pass

        player_avg_stats_qs = PlayerMatchStats.objects.filter(
            game_name=game_name
        ).values(
            'player_id',
            'player__username',
            'player__puuid'
        ).annotate(
            **aggregates_for_features
        ).filter(
            num_matches__gte=min_matches_for_analysis
        ).order_by('player_id')

        if not player_avg_stats_qs.exists():
            return Response({
                "analysis_details": {
                    "game_name": game_name, "eps": eps, "min_samples": min_samples,
                    "min_matches_per_player": min_matches_for_analysis,
                    "message": f"Нет данных для анализа DBSCAN для игры '{game_name}' с мин. {min_matches_for_analysis} матчей.",
                    "total_players_analyzed": 0, "clusters_found": 0, "noise_points": 0,
                    "features_used": ['combat_performance_score', 'avg_unique_game_abilities'],
                    "x_axis_label": "Combat Performance Score (масштаб.)",
                    "y_axis_label": "Avg Unique Game Abilities (масштаб.)"
                },
                "clustered_players": {}, "scatter_plot_data": []
            }, status=status.HTTP_200_OK)

        df = pd.DataFrame.from_records(list(player_avg_stats_qs))

        if has_direct_unique_field and 'avg_direct_unique_abilities' in df.columns and not df[
            'avg_direct_unique_abilities'].fillna(0).eq(0).all():
            df['avg_unique_game_abilities'] = df['avg_direct_unique_abilities']
            logger_views.info(f"DBSCAN для '{game_name}': Используются прямые значения 'avg_direct_unique_abilities'.")
        else:
            recalculated = False
            try:
                game_enum_value = GameNames(game_name).value
                if game_enum_value == GameNames.VALORANT.value and 'sum_skills_used' in df.columns and 'sum_ultimates_used' in df.columns:
                    df['avg_unique_game_abilities'] = safe_division_series(
                        df['sum_skills_used'].fillna(0) + df['sum_ultimates_used'].fillna(0),
                        df['num_matches']
                    )
                    logger_views.info(f"DBSCAN для '{game_name}': 'avg_unique_game_abilities' вычислено для Valorant.")
                    recalculated = True
                elif game_enum_value == GameNames.PUBG.value and 'sum_heals_used' in df.columns and 'sum_boosts_used' in df.columns:
                    df['avg_unique_game_abilities'] = safe_division_series(
                        df['sum_heals_used'].fillna(0) + df['sum_boosts_used'].fillna(0),
                        df['num_matches']
                    )
                    logger_views.info(f"DBSCAN для '{game_name}': 'avg_unique_game_abilities' вычислено для PUBG.")
                    recalculated = True
            except ValueError:
                pass

            if not recalculated:
                if 'avg_direct_unique_abilities' in df.columns:
                    df['avg_unique_game_abilities'] = df['avg_direct_unique_abilities']
                    logger_views.info(
                        f"DBSCAN для '{game_name}': 'avg_unique_game_abilities' взято из пустого/нулевого 'avg_direct_unique_abilities'.")
                else:
                    df['avg_unique_game_abilities'] = 0.0
                    logger_views.info(
                        f"DBSCAN для '{game_name}': 'avg_unique_game_abilities' установлено в 0 (нет данных или специфичной логики).")

        df['avg_unique_game_abilities'] = df['avg_unique_game_abilities'].fillna(0)
        if 'avg_direct_unique_abilities' in df.columns:
            df = df.drop(columns=['avg_direct_unique_abilities'])

        # пасчет combat_performance_score
        combat_score_components_data = {}
        base_combat_features = ['avg_kills', 'avg_kda', 'avg_damage_dealt', 'avg_headshot_rate']
        for feature_name in base_combat_features:
            if feature_name in df.columns and not df[feature_name].isnull().all():
                series = df[feature_name].fillna(df[feature_name].median())
                min_val, max_val = series.min(), series.max()
                combat_score_components_data[feature_name] = (series - min_val) / (
                            max_val - min_val) if max_val > min_val else pd.Series(0.5, index=df.index, dtype=float)
            else:
                combat_score_components_data[feature_name] = pd.Series(0.0, index=df.index, dtype=float)

        if 'avg_deaths' in df.columns and not df['avg_deaths'].isnull().all():
            deaths_series = df['avg_deaths'].fillna(df['avg_deaths'].median())
            min_deaths, max_deaths = deaths_series.min(), deaths_series.max()
            normalized_deaths = (deaths_series - min_deaths) / (
                        max_deaths - min_deaths) if max_deaths > min_deaths else pd.Series(0.5, index=df.index,
                                                                                           dtype=float)
            combat_score_components_data['inverted_deaths'] = 1 - normalized_deaths
        else:
            combat_score_components_data['inverted_deaths'] = pd.Series(0.0, index=df.index, dtype=float)

        combat_score_df = pd.DataFrame(combat_score_components_data)
        df['combat_performance_score'] = combat_score_df.sum(axis=1).fillna(0) if not combat_score_df.empty else 0.0

        features_for_dbscan_2d = ['combat_performance_score', 'avg_unique_game_abilities']
        x_axis_label = "Combat Performance Score (масштаб.)"
        y_axis_label = "Avg Unique Game Abilities (масштаб.)"

        missing_features_for_pca = [f for f in features_for_dbscan_2d if f not in df.columns]
        if missing_features_for_pca:
            logger_views.error(f"DBSCAN для '{game_name}': Отсутствуют колонки для анализа: {missing_features_for_pca}")
            return Response({
                "analysis_details": {"game_name": game_name,
                                     "message": f"Отсутствуют данные для фич: {', '.join(missing_features_for_pca)}",
                                     "total_players_analyzed": df.shape[0], "clusters_found": 0, "noise_points": 0,
                                     "features_used": features_for_dbscan_2d, "x_axis_label": x_axis_label,
                                     "y_axis_label": y_axis_label},
                "clustered_players": {}, "scatter_plot_data": []
            }, status=status.HTTP_200_OK)

        X = df[features_for_dbscan_2d].fillna(0).values
        if X.shape[0] < 1 or X.shape[1] != 2:
            return Response({
                "analysis_details": {"game_name": game_name, "message": "Не удалось сформировать 2D-данные.",
                                     "total_players_analyzed": X.shape[0], "clusters_found": 0, "noise_points": 0,
                                     "features_used": features_for_dbscan_2d, "x_axis_label": x_axis_label,
                                     "y_axis_label": y_axis_label},
                "clustered_players": {}, "scatter_plot_data": []
            }, status=status.HTTP_200_OK)

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        dbscan_model = DBSCAN(eps=eps, min_samples=min_samples)
        cluster_labels = dbscan_model.fit_predict(X_scaled)

        scatter_plot_data = [{"x": float(X_scaled[i, 0]), "y": float(X_scaled[i, 1]),
                              "cluster": int(cluster_labels[i]), "username": df.iloc[i]["player__username"]}
                             for i in range(X_scaled.shape[0])]

        results_for_response = []
        for index, row in df.iterrows():
            player_data_dict = {
                "player_id": int(row["player_id"]),
                "puuid": str(row.get("player__puuid", "")),
                "username": str(row["player__username"]),
                "game_name": game_name,
                "cluster": int(cluster_labels[index]),
                "num_matches": int(row.get("num_matches", 0)),
                "avg_kills": round(row.get('avg_kills', 0.0), 2),
                "avg_deaths": round(row.get('avg_deaths', 0.0), 2),
                "avg_assists": round(row.get('avg_assists', 0.0), 2),
                "avg_kda": round(row.get('avg_kda', 0.0), 2),
                "avg_headshot_rate": round(row.get('avg_headshot_rate', 0.0), 1),
                "avg_damage_dealt": round(row.get('avg_damage_dealt', 0.0), 1),
                "avg_unique_game_abilities": round(df.loc[index, 'avg_unique_game_abilities'], 2),
                "combat_performance_score": round(df.loc[index, 'combat_performance_score'], 2),
            }
            results_for_response.append(player_data_dict)

        serializer = DBSCANResultSerializer(data=results_for_response, many=True)
        if not serializer.is_valid():
            logger_views.error(f"Ошибка валидации сериализатора DBSCAN: {serializer.errors}")
            # логирование данных, которые не прошли валидацию
            if results_for_response:
                for i, item_data in enumerate(results_for_response):
                    temp_serializer = DBSCANResultSerializer(data=item_data)
                    if not temp_serializer.is_valid():
                        logger_views.error(f"DEBUG: Ошибка валидации для элемента {i}: {temp_serializer.errors}")
                        logger_views.error(f"DEBUG: Данные элемента {i}: {item_data}")
                        if i < 5:
                            pass
                        else:
                            break
            return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        final_clustered_players = defaultdict(list)
        for item in serializer.data:
            final_clustered_players[item['cluster']].append(item)
        sorted_final_clustered_players = {k: final_clustered_players[k] for k in sorted(final_clustered_players.keys())}

        return Response({
            "analysis_details": {
                "game_name": game_name, "eps": eps, "min_samples": min_samples,
                "min_matches_per_player": min_matches_for_analysis,
                "features_used": features_for_dbscan_2d,
                "total_players_analyzed": X_scaled.shape[0],
                "clusters_found": len(set(label for label in cluster_labels if label != -1)),
                "noise_points": int(np.sum(cluster_labels == -1)),
                "x_axis_label": x_axis_label, "y_axis_label": y_axis_label
            },
            "clustered_players": sorted_final_clustered_players,
            "scatter_plot_data": scatter_plot_data
        }, status=status.HTTP_200_OK)


class PlayerComparisonView(views.APIView):
    """API эндпоинт для сравнительного анализа игрока"""
    permission_classes = []

    def _calculate_player_avg_stats(self, player_stats_qs, game_name):
        if not player_stats_qs.exists():
            return None
        metrics_to_agg = {
            'avg_kills': Avg('kills'), 'avg_deaths': Avg('deaths'),
            'avg_assists': Avg('assists'), 'avg_kda': Avg('kda'),
            'avg_damage_dealt': Avg('damage_dealt'), 'avg_headshot_rate': Avg('headshot_rate')
        }
        if game_name == GameNames.VALORANT:
            metrics_to_agg.update({'avg_skills_used': Avg('skills_used'), 'avg_ultimates_used': Avg('ultimates_used')})
        elif game_name == GameNames.PUBG:
            metrics_to_agg.update({'avg_boosts_used': Avg('boosts_used'), 'avg_heals_used': Avg('heals_used')})

        aggregates = player_stats_qs.aggregate(**metrics_to_agg)
        for key, value in aggregates.items():
            if value is not None:
                aggregates[key] = round(value, 2)
        return aggregates

    def _calculate_group_stats_boundaries(self, group_stats_qs, game_name):
        if not group_stats_qs.exists():
            return None
        metrics_to_agg_expr = {
            'kills': (Min('kills'), Max('kills'), Avg('kills')),
            'deaths': (Min('deaths'), Max('deaths'), Avg('deaths')),
            'assists': (Min('assists'), Max('assists'), Avg('assists')), 'kda': (Min('kda'), Max('kda'), Avg('kda')),
            'damage_dealt': (Min('damage_dealt'), Max('damage_dealt'), Avg('damage_dealt')),
            'headshot_rate': (Min('headshot_rate'), Max('headshot_rate'), Avg('headshot_rate')),
        }
        if game_name == GameNames.VALORANT:
            metrics_to_agg_expr.update({
                'skills_used': (Min('skills_used'), Max('skills_used'), Avg('skills_used')),
                'ultimates_used': (Min('ultimates_used'), Max('ultimates_used'), Avg('ultimates_used')),
            })
        elif game_name == GameNames.PUBG:
            metrics_to_agg_expr.update({
                'boosts_used': (Min('boosts_used'), Max('boosts_used'), Avg('boosts_used')),
                'heals_used': (Min('heals_used'), Max('heals_used'), Avg('heals_used')),
            })
        agg_kwargs = {f'{metric}_{func}': expression for metric, expressions in metrics_to_agg_expr.items() for
                      func, expression in zip(['min', 'max', 'avg'], expressions)}
        aggregated_results = group_stats_qs.aggregate(**agg_kwargs)
        stats_boundaries = {}
        for metric in metrics_to_agg_expr.keys():
            stats_boundaries[f'avg_{metric}'] = {
                'min': round(aggregated_results.get(f'{metric}_min', 0) or 0, 2),
                'max': round(aggregated_results.get(f'{metric}_max', 0) or 0, 2),
                'avg': round(aggregated_results.get(f'{metric}_avg', 0) or 0, 2),
            }
        return stats_boundaries

    def get(self, request, *args, **kwargs):
        game_name = request.query_params.get('game_name')
        puuid = request.query_params.get('puuid')
        username = request.query_params.get('username')
        comparison_rank = request.query_params.get('comparison_rank')

        if not game_name:
            return Response({"error": "Параметр 'game_name' обязателен."}, status=status.HTTP_400_BAD_REQUEST)
        if not puuid and not username:
            return Response({"error": "Необходимо указать 'puuid' или 'username'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if puuid:
                target_player = Player.objects.get(puuid__iexact=puuid, game_name=game_name)
            else:
                target_player = Player.objects.filter(username__iexact=username, game_name=game_name).first()

            if not target_player:
                raise Player.DoesNotExist

        except Player.DoesNotExist:
            return Response({"error": "Игрок не найден."}, status=status.HTTP_404_NOT_FOUND)

        # считаем статистику игрока для сравнения
        player_latest_stats_qs = PlayerMatchStats.objects.filter(
            player=target_player
        ).order_by('-match__match_timestamp')[:20]

        target_player_avg_stats = self._calculate_player_avg_stats(player_latest_stats_qs, game_name)
        if not target_player_avg_stats:
            return Response({
                "error": f"Для игрока {target_player.username} не найдено достаточно матчей для анализа."
            }, status=status.HTTP_404_NOT_FOUND)

        # считаем статистику для группы сравнения
        comparison_group_boundaries = None
        player_count_in_rank = 0
        if comparison_rank:
            players_in_rank = Player.objects.filter(
                game_name=game_name,
                rank=comparison_rank
            ).exclude(id=target_player.id)

            player_count_in_rank = players_in_rank.count()

            if player_count_in_rank > 0:
                comparison_stats_qs = PlayerMatchStats.objects.filter(player__in=players_in_rank)
                comparison_group_boundaries = self._calculate_group_stats_boundaries(comparison_stats_qs, game_name)

        # получаем список всех доступных рангов
        available_ranks = list(Player.objects.filter(
            game_name=game_name, rank__isnull=False
        ).exclude(rank='').values_list('rank', flat=True).distinct().order_by('rank'))

        response_data = {
            "target_player": {
                "id": target_player.id,
                "username": target_player.username,
                "rank": target_player.rank,
                "stats": target_player_avg_stats,
                "matches_analyzed": player_latest_stats_qs.count()
            },
            "comparison_group": {
                "rank": comparison_rank,
                "player_count": player_count_in_rank,
                "stats_boundaries": comparison_group_boundaries
            },
            "available_ranks": available_ranks
        }

        return Response(response_data, status=status.HTTP_200_OK)