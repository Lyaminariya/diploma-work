import requests
import time
import os
import logging
import json
import random
from datetime import datetime, timezone

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from dotenv import load_dotenv

from stats_api.models import Player, Match, PlayerMatchStats, GameNames

load_dotenv()

PUBG_API_KEY = os.getenv("PUBG_API_KEY")
PUBG_API_BASE_URL = "https://api.pubg.com/shards"

REQUEST_DELAY = 6.1

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

if not PUBG_API_KEY:
    logger.error("PUBG_API_KEY не найден в переменных окружения")
else:
    logger.info("PUBG_API_KEY найден")

HEADERS = {
    "Authorization": f"Bearer {PUBG_API_KEY}",
    "Accept": "application/vnd.api+json"
}

def make_pubg_api_request(url, delay_multiplier=1):
    """Запрос к API с обработкой ошибок и лимитов"""
    logger.info(f"PUBG API Запрос: {url}")

    try:
        response = requests.get(url, headers=HEADERS)

        time.sleep(REQUEST_DELAY * delay_multiplier)

        if response.status_code == 429:
            retry_after_header = response.headers.get("Retry-After", "10")
            try:
                retry_after = int(retry_after_header)
            except ValueError:
                retry_after = 10

            logger.warning(f"PUBG API: Превышен лимит запросов. Ожидаем {retry_after} секунд")
            time.sleep(retry_after)

            response = requests.get(url, headers=HEADERS)
            time.sleep(REQUEST_DELAY * delay_multiplier)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.warning(f"PUBG API: Ресурс не найден (404) для URL: {url}")
            return None
        else:
            logger.error(f"PUBG API: Ошибка HTTP {response.status_code} для URL: {url}. Ответ: {response.text[:300]}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"PUBG API: Сетевая ошибка запроса к {url}: {e}")
        return None

def get_sample_match_ids(platform="steam", count=10):
    """Получает список последних матчей в игре"""
    url = f"{PUBG_API_BASE_URL}/{platform}/samples"
    data = make_pubg_api_request(url)

    match_ids = []

    if data and "data" in data and isinstance(data["data"], dict) and \
            "relationships" in data["data"] and \
            "matches" in data["data"]["relationships"] and \
            isinstance(data["data"]["relationships"]["matches"].get("data"), list):
        match_references = data["data"]["relationships"]["matches"]["data"]
        for match_ref in match_references:
            if match_ref and isinstance(match_ref, dict) and "id" in match_ref:
                match_ids.append(match_ref["id"])
        return match_ids[:count]

    logger.warning(f"Не удалось получить ID матчей из /samples на платформе {platform}. Ответ: {str(data)[:300]}")
    return []

def get_player_account_id_from_match(match_full_data, num_players_to_find=1):
    """Получает аккаунт игрока из матча"""
    player_account_ids = set()
    included_data = match_full_data.get("included", [])
    participants_api_data = [item for item in included_data if item and item.get("type") == "participant"]

    for participant_item in participants_api_data:
        p_stats = participant_item.get("attributes", {}).get("stats", {})
        actor_account_id = p_stats.get("playerId")
        if actor_account_id and actor_account_id.startswith("account."):
            player_account_ids.add(actor_account_id)

    if not player_account_ids:
        return []

    player_account_ids_list = list(player_account_ids)
    return random.sample(player_account_ids_list, min(num_players_to_find, len(player_account_ids_list)))

def get_player_match_ids(account_id, platform="steam", limit=200):
    """Получает список матчей игрока"""
    url = f"{PUBG_API_BASE_URL}/{platform}/players/{account_id}"
    data = make_pubg_api_request(url)
    if data and "data" in data and isinstance(data["data"], dict) and \
            "relationships" in data["data"] and "matches" in data["data"]["relationships"] and \
            isinstance(data["data"]["relationships"]["matches"].get("data"), list):
        match_references = data["data"]["relationships"]["matches"]["data"]
        return [match_ref["id"] for match_ref in match_references[:limit] if match_ref and "id" in match_ref]

    logger.warning(f"Не удалось получить список матчей для account_id {account_id}. Ответ: {str(data)[:200]}")
    return []


def get_player_rank_info(account_id, platform, season_id, game_mode_filter="squad-fpp"):
    """Получает ранг игрока"""
    if not season_id:
        logger.debug(f"Season ID не указан для {account_id}, ранг не будет получен")
        return "UNKNOWN"

    url = f"{PUBG_API_BASE_URL}/{platform}/players/{account_id}/seasons/{season_id}/ranked"
    data = make_pubg_api_request(url)
    if data and "data" in data and "attributes" in data["data"] and \
            "rankedGameModeStats" in data["data"]["attributes"]:
        ranked_stats_modes = data["data"]["attributes"]["rankedGameModeStats"]

        modes_to_check = [game_mode_filter]
        if "-" in game_mode_filter:
            base_mode = game_mode_filter.split("-")[0]
            if base_mode not in modes_to_check:
                modes_to_check.append(base_mode)

        for mode_key in modes_to_check:
            if mode_key in ranked_stats_modes and ranked_stats_modes[mode_key]:
                current_tier_info = ranked_stats_modes[mode_key].get("currentTier")
                if current_tier_info and current_tier_info.get("tier") and current_tier_info.get("subTier"):
                    tier = current_tier_info["tier"]
                    sub_tier = current_tier_info["subTier"]
                    if tier.lower() not in ["unranked", "none", ""]:
                        return f"{tier} {sub_tier}"

        logger.info(
            f"Актуальный ранг для режима(ов) '{', '.join(modes_to_check)}' не найден для {account_id} в сезоне {season_id}")
        return "UNRANKED"
    return "UNKNOWN"


def get_match_data(match_id, platform="steam"):
    """Получает информацию о матче"""
    url = f"{PUBG_API_BASE_URL}/{platform}/matches/{match_id}"
    data = make_pubg_api_request(url)
    if not data or "data" not in data:
        logger.warning(f"Не удалось получить данные матча для match_id: {match_id}. Ответ: {str(data)[:300]}")
        return None
    return data


class Command(BaseCommand):
    help = "Находит competitive матчи через /samples, извлекает игроков и собирает их статистику"

    def add_arguments(self, parser):
        parser.add_argument("--platform", type=str, default="steam", help="Платформа для поиска матчей")
        parser.add_argument("--sample_matches_to_check", type=int, default=10,
                            help="Сколько матчей из /samples проверить на 'competitive'")
        parser.add_argument("--players_from_match", type=int, default=1,
                            help="Сколько игроков взять из первого найденного competitive матча")
        parser.add_argument("--matches_per_player_to_save", type=int, default=2,
                            help="Сколько 'competitive'/'official' матчей сохранить для каждого найденного игрока")
        parser.add_argument("--season_id", type=str, help="ID сезона для получения ранга игроков")
        parser.add_argument("--game_mode_for_rank", type=str, default="squad-fpp",
                            help="Игровой режим для запроса ранга")
        parser.add_argument("--player_history_limit_multiplier", type=int, default=15,
                            help="Множитель для лимита запрашиваемых матчей из истории игрока (matches_per_player_to_save * multiplier)")

    def handle(self, *args, **options):
        platform = options["platform"]
        sample_matches_to_check_count = options["sample_matches_to_check"]
        players_from_match_count = options["players_from_match"]
        matches_per_player_to_save = options["matches_per_player_to_save"]
        current_season_id = options["season_id"]
        game_mode_for_rank_filter = options["game_mode_for_rank"]
        player_history_limit_multiplier = options["player_history_limit_multiplier"]

        logger.info(f"Начало поиска competitive матчей через /samples на платформе {platform}")

        if not PUBG_API_KEY:
            logger.error("PUBG_API_KEY не найден")
            return

        sample_match_ids = get_sample_match_ids(platform, count=sample_matches_to_check_count)
        if not sample_match_ids:
            logger.error("Не удалось получить ID матчей из /samples. Завершение")
            return

        logger.info(
            f"Получено {len(sample_match_ids)} ID матчей из /samples. Поиск первого competitive матча для извлечения игроков...")

        found_initial_players_ids = set()

        for sample_match_id_from_api in sample_match_ids:
            if len(found_initial_players_ids) >= players_from_match_count:
                logger.info("Найдено достаточно стартовых игроков")
                break

            logger.info(f"Запрос данных для сэмпл-матча: {sample_match_id_from_api}")

            match_full_data = get_match_data(sample_match_id_from_api, platform)
            if not match_full_data or "data" not in match_full_data:
                logger.warning(f"Не удалось получить данные для сэмпл-матча {sample_match_id_from_api}. Пропуск")
                continue

            match_attributes = match_full_data["data"].get("attributes")
            if not match_attributes:
                logger.warning(f"Отсутствуют атрибуты для сэмпл-матча {sample_match_id_from_api}. Пропуск")
                continue

            match_type_from_api = match_attributes.get("matchType", "").lower()
            if match_type_from_api == "competitive":
                logger.info(f"Найден competitive сэмпл-матч: {sample_match_id_from_api}. Извлечение игроков...")

                player_ids_in_match = get_player_account_id_from_match(match_full_data, players_from_match_count - len(
                    found_initial_players_ids))
                for pid in player_ids_in_match:
                    found_initial_players_ids.add(pid)

                logger.info(
                    f"Извлечено {len(player_ids_in_match)} игроков. Всего стартовых игроков: {len(found_initial_players_ids)}")
            else:
                logger.info(f"Сэмпл-матч {sample_match_id_from_api} (type: {match_type_from_api}) не competitive")

        if not found_initial_players_ids:
            logger.error(
                f"Не удалось найти стартовых игроков из {len(sample_match_ids)} проверенных сэмпл-матчей. Завершение")
            return

        logger.info(f"Найдено {len(found_initial_players_ids)} стартовых игроков: {found_initial_players_ids}")
        logger.info(f"Начало сбора {matches_per_player_to_save} подходящих матчей для каждого из них")

        processed_match_ids_in_session = set()
        total_player_match_stats_saved_this_session = 0

        for player_account_id_to_process in found_initial_players_ids:
            logger.info(f"Обработка стартового игрока: {player_account_id_to_process}")

            player_name_for_db = f"Player_{player_account_id_to_process[8:16]}"
            player_profile_data_url = f"{PUBG_API_BASE_URL}/{platform}/players/{player_account_id_to_process}"
            player_profile_data = make_pubg_api_request(player_profile_data_url)

            if player_profile_data and player_profile_data.get("data") and isinstance(player_profile_data.get("data"),
                                                                                      dict):
                player_name_for_db = player_profile_data["data"].get("attributes", {}).get("name", player_name_for_db)

            player_rank_str_for_start_player = "UNKNOWN"
            if current_season_id:
                player_rank_str_for_start_player = get_player_rank_info(player_account_id_to_process, platform,
                                                                        current_season_id,
                                                                        game_mode_for_rank_filter)

            start_player_obj, player_created = Player.objects.update_or_create(
                puuid=player_account_id_to_process, game_name=GameNames.PUBG,
                defaults={"username": player_name_for_db,
                          "rank": player_rank_str_for_start_player}
            )

            logger.info(
                f"Игрок (стартовый): {start_player_obj.username}, Ранг ({game_mode_for_rank_filter}, сезон {current_season_id or 'N/A'}): {start_player_obj.rank}")

            # Проверка ранга стартового игрока
            if not start_player_obj.rank or start_player_obj.rank in ["UNKNOWN", "UNRANKED"]:
                logger.warning(
                    f"Стартовый игрок {start_player_obj.username} ({player_account_id_to_process}) имеет ранг '{start_player_obj.rank}'. Его матчи не будут обрабатываться.")
                continue

            history_limit = matches_per_player_to_save * player_history_limit_multiplier
            logger.info(f"Запрос до {history_limit} матчей из истории для игрока {start_player_obj.username}...")

            player_specific_match_ids = get_player_match_ids(player_account_id_to_process, platform,
                                                             limit=history_limit)
            if not player_specific_match_ids:
                logger.warning(f"Не найдено матчей в истории для игрока {start_player_obj.username}. Пропуск игрока")
                continue

            loaded_matches_for_this_player_count = 0
            for match_id_from_player_history in player_specific_match_ids:
                if loaded_matches_for_this_player_count >= matches_per_player_to_save:
                    logger.info(
                        f"Для игрока {start_player_obj.username} сохранено достаточно матчей ({loaded_matches_for_this_player_count})")
                    break

                logger.info(
                    f"Запрос данных для матча {match_id_from_player_history} из истории игрока {start_player_obj.username}")

                match_full_data_player_history = get_match_data(match_id_from_player_history, platform)
                if not match_full_data_player_history or "data" not in match_full_data_player_history:
                    logger.warning(f"Не удалось получить данные для матча {match_id_from_player_history}. Пропуск.")
                    continue

                match_main_data_player_history = match_full_data_player_history["data"]
                match_attributes_player_history = match_main_data_player_history.get("attributes")
                included_data_player_history = match_full_data_player_history.get("included", [])

                if not match_attributes_player_history:
                    logger.warning(f"Отсутствуют атрибуты для матча {match_id_from_player_history}. Пропуск")
                    continue

                match_type_player_history = match_attributes_player_history.get("matchType", "").lower()
                is_custom_match_player_history = match_attributes_player_history.get("isCustomMatch", False)
                game_mode_api_player_history = match_attributes_player_history.get("gameMode", "unknown").lower()

                is_match_suitable = False
                if match_type_player_history == "competitive":
                    is_match_suitable = True
                elif match_type_player_history == "official" and not is_custom_match_player_history:
                    if game_mode_api_player_history in ["squad", "squad-fpp", "solo", "solo-fpp", "duo", "duo-fpp"]:
                        is_match_suitable = True

                if not is_match_suitable:
                    logger.info(
                        f"Матч {match_id_from_player_history} (type: {match_type_player_history}, mode: {game_mode_api_player_history}, custom: {is_custom_match_player_history}) не является подходящим. Пропуск.")
                    continue

                logger.info(
                    f"Матч {match_id_from_player_history} (type: {match_type_player_history}) является подходящим. Обработка...")

                match_timestamp_str = match_attributes_player_history.get("createdAt")
                match_timestamp = parse_datetime(match_timestamp_str) if match_timestamp_str else datetime.now(
                    timezone.utc)
                duration = match_attributes_player_history.get("duration", 0)

                match_obj_db, match_created_in_db = Match.objects.update_or_create(
                    game_match_id=match_id_from_player_history, game_name=GameNames.PUBG,
                    defaults={
                        "match_timestamp": match_timestamp, "duration_seconds": duration,
                        "map_name": match_attributes_player_history.get("mapName"),
                        "game_mode": game_mode_api_player_history,
                        "is_ranked": True,
                    }
                )

                is_new_match_for_session = match_id_from_player_history not in processed_match_ids_in_session

                if is_new_match_for_session:
                    if match_created_in_db:
                        logger.info(
                            f"Подходящий Матч PUBG {match_id_from_player_history} ({match_obj_db.map_name}) добавлен в БД")

                participants_api_data = [item for item in included_data_player_history if
                                         item and item.get("type") == "participant"]
                rosters_api_data = [item for item in included_data_player_history if
                                    item and item.get("type") == "roster"]

                if not participants_api_data:
                    logger.warning(f"В матче {match_id_from_player_history} отсутствуют данные участников")
                    if is_new_match_for_session:
                        processed_match_ids_in_session.add(match_id_from_player_history)
                        continue

                roster_win_map = {}
                if rosters_api_data:
                    for roster_item in rosters_api_data:
                        roster_id = roster_item.get("id")
                        if not roster_id:
                            continue

                        r_stats = roster_item.get("attributes", {}).get("stats", {})
                        rank_val = r_stats.get("rank")

                        try:
                            rank_int = int(rank_val) if rank_val is not None else 99
                        except ValueError:
                            rank_int = 99

                        roster_win_map[roster_id] = (rank_int == 1)

                for participant_item in participants_api_data:
                    p_stats = participant_item.get("attributes", {}).get("stats", {})
                    actor_account_id_loop = p_stats.get("playerId")

                    if actor_account_id_loop == player_account_id_to_process:
                        logger.debug(
                            f"Сбор статистики для целевого игрока: {start_player_obj.username} ({actor_account_id_loop}) в матче {match_id_from_player_history}")

                        kills = p_stats.get("kills", 0)
                        assists = p_stats.get("assists", 0)
                        death_type = p_stats.get("deathType", "")
                        deaths = 1 if death_type and death_type.lower() not in ["", "alive"] else 0
                        headshot_kills = p_stats.get("headshotKills", 0)
                        hs_rate = (headshot_kills / kills) * 100 if kills > 0 else 0.0
                        boosts_used = p_stats.get("boosts", 0)
                        heals_used = p_stats.get("heals", 0)
                        kda_val = (kills + assists) / deaths if deaths > 0 else (kills + assists)

                        won_match = False
                        participant_api_id_loop = participant_item.get("id")
                        if rosters_api_data:
                            for roster_item_loop in rosters_api_data:
                                if not roster_item_loop:
                                    continue

                                roster_id_loop = roster_item_loop.get("id")
                                for p_ref_loop in roster_item_loop.get("relationships", {}).get("participants", {}).get(
                                        "data", []):
                                    if p_ref_loop and p_ref_loop.get("id") == participant_api_id_loop:
                                        won_match = roster_win_map.get(roster_id_loop, False)
                                        break

                                if roster_id_loop and roster_id_loop in roster_win_map:
                                    if participant_api_id_loop in [p_l["id"] for p_l in
                                                                   roster_item_loop.get("relationships", {}).get(
                                                                       "participants", {}).get("data", []) if p_l]:
                                        break

                        stat_obj, stat_created = PlayerMatchStats.objects.update_or_create(
                            player=start_player_obj,
                            match=match_obj_db,
                            defaults={
                                "game_name": GameNames.PUBG, "won_match": won_match,
                                "kills": kills, "deaths": deaths, "assists": assists,
                                "kda": round(kda_val, 2), "headshot_rate": round(hs_rate, 1),
                                "damage_dealt": round(p_stats.get("damageDealt", 0.0), 1),
                                "boosts_used": boosts_used, "heals_used": heals_used,
                                "revives": p_stats.get("revives", 0), "dbnos": p_stats.get("DBNOs", 0),
                                "time_alive_seconds": int(p_stats.get("timeSurvived", 0)),
                                "longest_kill_distance": round(p_stats.get("longestKill", 0.0), 1)
                            }
                        )

                        if stat_created:
                            total_player_match_stats_saved_this_session += 1

                        break

                if is_new_match_for_session:
                    processed_match_ids_in_session.add(match_id_from_player_history)

                loaded_matches_for_this_player_count += 1
                logger.info(
                    f"Обработка матча {match_id_from_player_history} для стартового игрока {start_player_obj.username} завершена. Подходящих матчей для него: {loaded_matches_for_this_player_count}/{matches_per_player_to_save}")

        logger.info(
            f"Загрузка данных PUBG завершена. Всего записей статистики игроков за матч создано/обновлено в этой сессии: {total_player_match_stats_saved_this_session}. Уникальных матчей добавлено в БД (если были новые): {len(processed_match_ids_in_session)}")
