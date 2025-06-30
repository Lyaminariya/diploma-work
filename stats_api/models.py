from django.db import models


class GameNames(models.TextChoices):
    VALORANT = "valorant", "Valorant"
    PUBG = "pubg", "PUBG"

class Player(models.Model):
    game_name = models.CharField(max_length=20, choices=GameNames.choices, default=GameNames.VALORANT, help_text="Название игры")
    puuid = models.CharField(max_length=80, unique=True, db_index=True, null=True, blank=True, verbose_name="PUUID", help_text="Уникальный идентификатор игрока")
    username = models.CharField(max_length=100, unique=False, db_index=True, null=True, blank=True, help_text="Никнейм игрока")
    created_at = models.DateTimeField(auto_now_add=True)
    rank = models.CharField(max_length=100, unique=False, db_index=True, null=True, blank=True, help_text="Ранг игрока")

    class Meta:
        verbose_name = "Игрок"
        verbose_name_plural = "Игроки"
        ordering = ["username"]
        unique_together = ("puuid", "game_name")

    def __str__(self):
        game_name = f"[{self.get_game_name_display()}]"
        if self.username:
            return f"{game_name} {self.username}"
        elif self.puuid:
            return f"{game_name} игрок (PUUID: {self.puuid})"
        else:
            return f"{game_name} игрок (ID в БД: {self.id})"

class Match(models.Model):
    game_name = models.CharField(max_length=20, choices=GameNames.choices, default=GameNames.VALORANT, help_text="Название игры")
    game_match_id = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    match_timestamp = models.DateTimeField(db_index=True, null=True, help_text="Дата и время начала игры")
    duration_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="Продолжительность игры (в секундах)")
    map_name = models.CharField(max_length=100, blank=True, null=True, help_text="Название карты")
    rounds_played = models.PositiveIntegerField(null=True, blank=True, help_text="Количество сыгранных раундов")
    game_mode = models.CharField(max_length=150, blank=True, null=True, help_text="Режим игры")
    is_ranked = models.BooleanField(blank=True, null=True, help_text="Является ли матч ранговым")

    class Meta:
        ordering = ["-match_timestamp"]
        unique_together = ("game_match_id", "game_name")

    def __str__(self):
        game_name = f"[{self.get_game_name_display()}]"
        mode = f"({self.game_mode.split('/')[-1].replace('РежимИгры', '')})" if self.game_mode else ""
        timestamp_str = self.match_timestamp.strftime('%Y-%m-%d %H:%M') if self.match_timestamp else "Нет временной метки"
        return f"{game_name} матч {self.id or self.game_match_id}{mode}, временная метка {timestamp_str}"

class PlayerMatchStats(models.Model):
    game_name = models.CharField(max_length=20, choices=GameNames.choices, default=GameNames.VALORANT, help_text="Название игры")
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="match_stats")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="match_stats")
    won_match = models.BooleanField(default=False, help_text="Выиграл ли игрок этот матч?")

    # Основные показатели
    kills = models.PositiveIntegerField(default=0)
    deaths = models.PositiveIntegerField(default=0)
    assists = models.PositiveIntegerField(default=0)
    kda = models.FloatField(default=0.0)
    headshot_rate = models.FloatField(default=0.0, help_text="Процент выстрелов в голову от общих попаданий")
    damage_dealt = models.PositiveIntegerField(default=0.0, help_text="Нанесенный урон")
    unique_abilities_used = models.PositiveIntegerField(default=0, help_text="Использованные уникальные возможности игры")

    # Время
    time_alive_seconds = models.PositiveIntegerField(default=0, null=True, blank=True, help_text="Общее время жизни в матче в секундах")

    # Valorant поля
    # Умения
    skills_used = models.PositiveIntegerField(default=0, null=True, blank=True, help_text="Общее кол-во примененных умений (кроме ультимейтов)")
    ultimates_used = models.PositiveIntegerField(default=0, null=True, blank=True, help_text="Кол-во примененных ультимейтов")

    # Цели (бомба)
    bomb_plants = models.PositiveIntegerField(default=0, null=True, blank=True, help_text="Сколько раз установил бомбу")
    bomb_defuses = models.PositiveIntegerField(default=0, null=True, blank=True, help_text="Сколько раз обезвредил бомбу")

    # Точность
    headshots = models.PositiveIntegerField(default=0, null=True, blank=True)
    bodyshots = models.PositiveIntegerField(default=0, null=True, blank=True)
    legshots = models.PositiveIntegerField(default=0, null=True, blank=True)
    total_shots_hitted = models.PositiveIntegerField(default=0, null=True, blank=True, help_text="Всего выстрелов попали")
    total_shots_fired = models.PositiveIntegerField(default=0, null=True, blank=True, help_text="Всего выстрелов сделано")

    # Оружие
    primary_weapon_used = models.CharField(max_length=100, null=True, blank=True, help_text="Основное/самое результативное оружие")

    # Броня
    armor_lvl1_purchases = models.PositiveIntegerField(default=0, null=True, blank=True, help_text="Сколько раз купил броню 1 ур.")
    armor_lvl2_purchases = models.PositiveIntegerField(default=0, null=True, blank=True, help_text="Сколько раз купил броню 2 ур.")

    # PUBG поля
    boosts_used = models.PositiveIntegerField(default=0, null=True, blank=True,help_text="Количество использованных усилений")
    heals_used = models.PositiveIntegerField(default=0, null=True, blank=True, help_text="Количество использованных усилений лечений")
    revives = models.PositiveIntegerField(default=0, null=True, blank=True, help_text="Количество воскрешенных союзников")
    dbnos = models.PositiveIntegerField(default=0, null=True, blank=True, help_text="Down But Not Out - количество нокаутов")
    longest_kill_distance = models.PositiveIntegerField(default=0, null=True, blank=True, help_text="Самое дальнее убийство")


    class Meta:
        unique_together = ("player", "match")

        ordering = ["-match__match_timestamp"]
        verbose_name = "Статистика игрока за матч"
        verbose_name_plural = "Статистика игроков за матчи"

    def save(self, *args, **kwargs):
        if not self.game_name:
            if self.match:
                self.game_name = self.match.game_name
            elif self.player:
                self.game_name = self.player.game_name
        super().save(*args, **kwargs)

    def __str__(self):
        game_name = f"[{self.get_game_name_display()}]"
        player_name = self.player.username if self.player else "N/A"
        match_id_str = self.match.game_match_id if self.match else "N/A"
        win_status = "Победа" if self.won_match else "Проигрыш"
        return f"{game_name} {player_name} в матче {match_id_str} - {win_status}"
