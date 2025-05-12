import requests
import time
import os
import logging
from datetime import datetime, timezone
from collections import deque, defaultdict, Counter

from django.core.management.base import BaseCommand

from dotenv import load_dotenv

from stats_api.models import Player, Match, PlayerMatchStats


load_dotenv()

API_BASE_URL = "https://api.henrikdev.xyz"

# Задержка для запросов
REQUEST_DELAY = 2.1

# Настройки логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Конфигурация
HENRIKDEV_API_KEY = os.getenv("HENRIKDEV_API_KEY")
if not HENRIKDEV_API_KEY:
    logger.error("HENRIKDEV_API_KEY не найден в переменных окружения")
else:
    logger.info("HENRIKDEV_API_KEY найден")

HEADERS = {
    "Authorization": HENRIKDEV_API_KEY,
    "accept": "application/json"
}

RANK_TIERS = {
    "IRON": list(range(3, 6)),
    "BRONZE": list(range(6, 9)),
    "SILVER": list(range(9, 12)),
    "GOLD": list(range(12, 15)),
    "PLATINUM": list(range(15, 18)),
    "DIAMOND": list(range(18, 21)),
    "ASCENDANT": list(range(21, 24)),
    "IMMORTAL": list(range(24, 27)),
    "RADIANT": [27],
}

def get_rank_name(tier):
    """Получает ранг из числа ранга"""
    if not isinstance(tier, int):
        return "UNKNOWN"

    for name, tiers in RANK_TIERS.items():
        if tier in tiers:
            return name

    if tier < 3:
        return "UNRANKED"
    return "UNKNOWN"

def make_api_request(url):
    """Запрос к API с обработкой ошибок и лимитов"""
    logger.info(f"Запрос к API: {url}")

    try:
        response = requests.get(url, headers=HEADERS)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5)) # Получаем время ожидания из заголовка
            logger.warning(f"Превышен лимит запросов. Ожидаем {retry_after} секунд")
            time.sleep(retry_after)

            response = requests.get(url, headers=HEADERS)

        if response.status_code == 200:
            try:
                data = response.json()

                # Проверка на внутренние ошибки API
                if isinstance(data, dict) and data.get("status") and data.get("status") != 200:
                    errors = data.get("errors")
                    error_msg = errors.get("message")
                    logger.error(f"Ошибка от API ({data.get('status')}): {error_msg} для URL: {url}")
                    if errors:
                        logger.error(f"Детали: {errors['details']}")
                    return None
                return data
            except requests.exceptions.JSONDecodeError:
                logger.error(f"Не удалось декодировать JSON из ответа для URL: {url}. Ответ: {response.text[:500]}...")
                return None
        else:
            logger.error(f"Ошибка HTTP {response.status_code} для URL: {url}. Ответ: {response.text[:500]}...")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Сетевая ошибка запроса к API {url} : {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запросе к API {url}: {e}")
        return None

def get_account_details(name, tag):
    """Получает данные аккаунта по Riot ID"""
    url = f"{API_BASE_URL}/valorant/v1/account/{name}/{tag}"
    data = make_api_request(url)
    if data and data.get("status") == 200 and "data" in data:
        return data["data"]
    return None

# def get_player_mmr_by_puuid(region, puuid):
#     """Получает текущий ранг игрока по PUUID и региону"""
#     url = f'/valorant/v3/mmr/by-puuid/{region}/{puuid}'
#     data = make_api_request(url)
#     if data and data.get('status') == 200 and isinstance(data.get('data'), dict):
#         mmr_data = data['data']
#         current_tier = (mmr_data.get('current_data', {}).get or mmr_data.get('currenttier'))
#         rank_name = get_rank_name(current_tier)
#         return rank_name, current_tier
#     return 'UNKNOWN', None

def get_matches_by_puuid(region, puuid, platform="pc", count=20):
    """Получает список последних матчей игрока"""
    logger.info(f"Формирование URL для get_matches_by_puuid (v4): region={region}, puuid={puuid}, platform={platform}, mode=competitive, count={count}")

    url = f"{API_BASE_URL}/valorant/v4/by-puuid/matches/{region}/{platform}/{puuid}?mode=competitive&size={count}"
    logger.info(f"Сформированный URL: {url}")
    data = make_api_request(url)
    if data and data.get("status") == 200 and "data" in data and isinstance(data["data"], list):
        return data["data"]

    logger.warning(f"Не удалось получить историю матчей для PUUID {puuid} в регионе {region}. Ответ: {data}")
    return []

def get_match_details(match_id):
    """Получает детальную информацию о матче"""
    url = f"{API_BASE_URL}/valorant/v2/match/{match_id}"
    data = make_api_request(url)
    if data and data.get("status") == 200 and "data" in data:
        return data["data"]
    return None

class Command(BaseCommand):
    help = "Загружает данные о матчах Valorant из API и сохраняет их в БД"

    def add_arguments(self, parser):
        parser.add_argument("--players_per_rank", type=int, default=5, help="Сколько игроков каждого ранга пытаться найти")
        parser.add_argument("--matches_per_player", type=int, default=5, help="Сколько последних матчей для игрока пытаться загружать")
        parser.add_argument("--start_name", type=str, required=True, help="Имя игрока (без тэга) для начала поиска")
        parser.add_argument("--start_tag", type=str, required=True, help="Тэг игрока (без #) для начала поиска")
        parser.add_argument("--target_ranks", nargs="+", default=["GOLD", "PLATINUM", "DIAMOND"], help="Список рангов для поиска")

    def handle(self, *args, **options):
        players_per_rank = options["players_per_rank"]
        matches_per_player = options["matches_per_player"]
        start_name = options["start_name"]
        start_tag = options["start_tag"]
        target_ranks_input = [rank.upper() for rank in options["target_ranks"]]
        platform = "pc"

        logger.info(f"Начало загрузки данных. Цель: {players_per_rank} игроков для рангов {target_ranks_input}, по {matches_per_player} матчей")
        logger.info(f"Стартовый игрок: {start_name}#{start_tag}")

        target_ranks = {rank_name: players_per_rank for rank_name in target_ranks_input if rank_name in RANK_TIERS}
        if not target_ranks:
            logger.error(f"Не указано ни одного корректного ранга. Завершение")
            return

        start_account_data = get_account_details(start_name, start_tag)
        if not start_account_data or "puuid" not in start_account_data or "region" not in start_account_data:
            logger.error(f"Не удалось получить PUUID или регион для стартового игрока {start_name}#{start_tag}. Проверьте Riot ID и регион")
            return

        start_puuid = start_account_data["puuid"]
        start_region = start_account_data["region"]
        logger.info(f"Стартовый игрок {start_name}#{start_tag}, PUUID={start_puuid}, регион={start_region}")

        # Поиск игроков
        found_players_by_rank = defaultdict(set)

        puuids_to_process = deque([(start_puuid, start_region)])
        processed_puuids = {start_puuid}
        player_region_map = {start_puuid: start_region}

        max_iterations = 500
        iterations = 0

        logger.info("Начало поиска игроков")

        while puuids_to_process and iterations < max_iterations:
            iterations += 1

            all_filled = all(len(found_players_by_rank.get(rank, set())) >= count for rank, count in target_ranks.items())
            if all_filled:
                logger.info("Найдено достаточно игроков")
                break

            current_puuid, current_region = puuids_to_process.popleft()
            logger.info(f"Обработка PUUID: {current_puuid}. Регион {current_region}")

            matches_for_crawl = get_matches_by_puuid(current_region, current_puuid, platform=platform, count=5)
            logger.info(f"Для {current_puuid} найдено {len(matches_for_crawl)} матчей для сканирования")

            for match_summary in matches_for_crawl:
                match_id = match_summary.get("match_id")
                if not match_id:
                    match_meta = match_summary.get("metadata")
                    if not match_meta:
                        continue
                    match_id = match_meta.get("match_id")
                    if not match_id:
                        continue

                match_details = get_match_details(match_id)
                if not match_details or "players" not in match_details or "all_players" not in match_details["players"]:
                    continue

                match_region = match_details.get("metadata", {}).get("region", current_region)

                for player_data in match_details["players"]["all_players"]:
                    participant_puuid = player_data.get("puuid")
                    if not participant_puuid or len(participant_puuid) < 10:
                        continue

                    # Получаем ранг игрока в этом матче
                    participant_rank_tier = player_data.get("currenttier_patched", {})
                    participant_rank_name = participant_rank_tier.split()[0].upper()

                    logger.info(f"Игрок: {player_data.get('name')}#{player_data.get('tag')}, Ранг: {participant_rank_tier}, Имя ранга: {participant_rank_name}")

                    if participant_rank_name in target_ranks and len(found_players_by_rank.get(participant_rank_name, set())) < target_ranks[participant_rank_name]:
                        if participant_puuid not in found_players_by_rank[participant_rank_name]:
                            found_players_by_rank[participant_rank_name].add(participant_puuid)
                            player_region_map[participant_puuid] = match_region

                            logger.info(
                                f"Найден игрок {player_data.get('name', '?')}#{player_data.get('tag', '?')} (PUUID: {participant_puuid} с рангом {participant_rank_name}"
                                f"({len(found_players_by_rank[participant_rank_name])}/{target_ranks[participant_rank_name]}. Регион {match_region}"
                            )

                        # Добавляем в очередь и в обработанные всех новых игроков, даже если их ранг неподходящий
                        if participant_puuid not in processed_puuids:
                            processed_puuids.add(participant_puuid)
                            player_region_map[participant_puuid] = match_region
                            puuids_to_process.append((participant_puuid, match_region))

        logger.info("Поиск игроков завершен")
        if iterations >= max_iterations:
            logger.warning("Достигнут лимит итераций поиска")

        # Итоговый список PUUID для загрузки матча
        final_puuids_to_load = set()
        for rank, puuids_set in found_players_by_rank.items():
            final_puuids_to_load.update(list(puuids_set)[:players_per_rank])
            logger.info(f"Для ранга {rank} найдено: {len(puuids_set)} игроков")

        if not final_puuids_to_load:
            logger.warning("Не найдено ни одного подходящего игрока для загрузки матчей")
            return

        logger.info(f"Всего уникальных игроков для загрузки 'competitive' матчей: {len(final_puuids_to_load)}")

        # Загрузка матчей для найденных игроков
        total_matches_processed = 0
        processed_match_ids = set()

        for puuid in final_puuids_to_load:
            region = player_region_map.get(puuid, start_region)
            logger.info(f"Загрузка {matches_per_player} матчей для игрока: {puuid}. Регион {region}")

            matches_list = get_matches_by_puuid(region, puuid, count=matches_per_player)
            if not matches_list:
                logger.warning(f"Не найдено матчей для игрока {puuid}. Пропуск")
                continue

            match_ids_to_process = [m.get("metadata", {}).get("match_id") for m in matches_list]
            logger.info(f"Найдено {len(match_ids_to_process)} ID матчей для игрока {puuid}")

            # Обработка каждого матча
            for match_id in match_ids_to_process:
                if match_id in processed_match_ids:
                    logger.info(f"Матч {match_id} уже обработан в этой сессии. Пропуск")
                    continue

                logger.info(f"Обработка матча: {match_id}")

                match_details = get_match_details(match_id)
                if not match_details:
                    logger.warning(f"Не удалось получить детали матча {match_id}. Пропуск")
                    continue

                metadata = match_details.get("metadata")
                players_info = match_details.get("players", {}).get("all_players", [])
                teams_info = match_details.get("teams", {})
                rounds_info = match_details.get("rounds", [])

                if not metadata or not players_info or not teams_info or not rounds_info:
                    logger.warning(f"Неполные данные в ответе для матча {match_id}. Пропуск")
                    continue

                # Конвертируем время начала матча
                match_datetime = metadata.get("game_start")
                match_datetime_str = datetime.fromtimestamp(match_datetime, tz=timezone.utc)

                game_lenght = metadata.get("game_length", 0)
                map_name = metadata.get("map", {})
                rounds_played = metadata.get("rounds_played", 0)
                game_mode = metadata.get("mode", {})
                is_ranked_flag = metadata.get("mode_id", {}) == "competitive"

                match_obj, match_created = Match.objects.update_or_create(
                    game_match_id=match_id,
                    defaults={
                        "match_timestamp": match_datetime_str,
                        "duration_seconds": game_lenght,
                        "map_name": map_name,
                        "rounds_played": rounds_played,
                        "game_mode": game_mode,
                        "is_ranked": is_ranked_flag,
                    }
                )

                action_match = "добавлен" if match_created else "обновлен"
                logger.info(f"Матч {match_id} ({map_name}) {action_match}")

                plants_by_puuid = defaultdict(int)
                defuses_by_puuid = defaultdict(int)
                weapon_usage_by_puuid = defaultdict(list)

                for round_data in rounds_info:
                    plant_info = round_data.get("plant_events", {})
                    defuse_info = round_data.get("defuse_events", {})
                    if plant_info:
                        if plant_info["planted_by"] is not None:
                            planter_puuid = plant_info["planted_by"].get("puuid")
                            if planter_puuid:
                                plants_by_puuid[planter_puuid] += 1
                    if defuse_info:
                        if defuse_info["defused_by"] is not None:
                            defuser_puuid = defuse_info["defused_by"].get("puuid")
                            if defuser_puuid:
                                defuses_by_puuid[defuser_puuid] += 1

                    for player_round_stats in round_data.get("player_stats", []):
                        puuid = player_round_stats.get("player_puuid")
                        if not puuid:
                            continue

                        economy_data = player_round_stats.get("economy", {})
                        if not economy_data:
                            continue

                        weapon_data = economy_data.get("weapon")
                        if weapon_data and weapon_data.get("name"):
                            weapon_name = weapon_data["name"]

                            # Исключаем стартовое оружие (Classic, Knife и т.д.)
                            if weapon_name.lower() not in ["classic", "knife"]:
                                weapon_usage_by_puuid[puuid].append(weapon_name)

                if teams_info["red"].get("has_won"):
                    winning_team = "Red"
                else:
                    winning_team = "Blue"

                for player_data in players_info:
                    participant_puuid = player_data.get("puuid")
                    if not participant_puuid or len(participant_puuid) < 10:
                        continue

                    p_name = player_data.get("name", f"Игрок_{participant_puuid}")
                    p_tag = player_data.get("tag", f"EUW")
                    p_rank = player_data.get("currenttier", 0)
                    p_username = f"{p_name}#{p_tag}"
                    p_team = player_data.get("team")

                    participant_obj, p_created = Player.objects.update_or_create(
                        puuid=participant_puuid,
                        defaults={
                            "username": p_username,
                            "rank": p_rank,
                        }
                    )

                    if p_created:
                        logger.info(f"Создан/найден участник матча: {p_username}")

                    # Получаем статистику
                    stats = player_data.get("stats")
                    if not isinstance(stats, dict):
                        logger.warning(f"Отсутствует статистика для {participant_obj.username} в матче {match_id}")
                        continue

                    # Определяем победу
                    player_won = (p_team == winning_team)

                    kills = stats.get("kills", 0)
                    deaths = stats.get("deaths", 0)
                    assists = stats.get("assists", 0)
                    if deaths == 0:
                        kda = kills + assists
                    else:
                        kda = round((kills + assists) / deaths, 2)

                    ability_casts = player_data.get("ability_casts", {}) or {}
                    skills_used = (ability_casts.get("q_cast", 0) +
                                   ability_casts.get("e_cast", 0) +
                                   ability_casts.get("c_cast", 0))
                    ultimates_used = ability_casts.get("x_cast", 0)

                    headshots = stats.get("headshots", 0)
                    bodyshots = stats.get("bodyshots", 0)
                    legshots = stats.get("legshots", 0)
                    total_shots_hitted = headshots + bodyshots + legshots
                    headshot_rate = round(headshots / total_shots_hitted, 2)

                    bomb_plants = plants_by_puuid.get(participant_puuid, 0)
                    bomb_defuses = defuses_by_puuid.get(participant_puuid, 0)

                    player_weapon_kills = weapon_usage_by_puuid.get(participant_puuid)
                    favorite_weapon_name = None
                    if player_weapon_kills:
                        weapon_counter = Counter(player_weapon_kills)
                        most_common = weapon_counter.most_common()
                        if most_common:
                            if most_common[0][0]:
                                favorite_weapon_name = most_common[0][0]
                            elif len(most_common) > 1 and most_common[1][0]:
                                favorite_weapon_name = most_common[1][0]

                    stats_obj, stat_created = PlayerMatchStats.objects.update_or_create(
                        player=participant_obj,
                        match=match_obj,
                        defaults={
                            "won_match": player_won,
                            "kills": kills,
                            "deaths": deaths,
                            "kda": kda,
                            "assists": assists,
                            "skills_used": skills_used,
                            "ultimates_used": ultimates_used,
                            "bomb_plants": bomb_plants,
                            "bomb_defuses": bomb_defuses,
                            "headshots": headshots,
                            "bodyshots": bodyshots,
                            "legshots": legshots,
                            "headshot_rate": headshot_rate,
                            "total_shots_hitted": total_shots_hitted,
                            "primary_weapon_used": favorite_weapon_name or "",
                        }
                    )

                    action_stat = "Создана" if stat_created else "Обновлена"
                    logger.info(f"{action_stat} для {p_username}")

                processed_match_ids.add(match_id)
                total_matches_processed += 1

            logger.info(f"Обработка игрока {puuid} завершена")

        logger.info(f"Загрузка данных полностью завершена. Всего уникальных матчей обработано/обновлено в этой сессии: {len(processed_match_ids)}")
