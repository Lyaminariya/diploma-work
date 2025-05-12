from django.db import models


class Player(models.Model):
    puuid = models.CharField(max_length=80, unique=True, db_index=True, null=True, blank=True, verbose_name="PUUID", help_text="Уникальный идентификатор игрока")
    username = models.CharField(max_length=100, unique=False, db_index=True, null=True, blank=True, help_text="Никнейм игрока")
    created_at = models.DateTimeField(auto_now_add=True)
    rank = models.CharField(max_length=100, unique=False, db_index=True, null=True, blank=True, help_text="Ранг игрока")

    class Meta:
        verbose_name = "Игрок"
        verbose_name_plural = "Игроки"
        ordering = ["username"]

    def __str__(self):
        if self.username:
            return self.username
        elif self.puuid:
            return f"Игрок (PUUID: {self.puuid})"
        else:
            return f"Игрок (ID: {self.id})"

class Match(models.Model):
    game_match_id = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    match_timestamp = models.DateTimeField(db_index=True, null=True, help_text="Дата и время начала игры")
    duration_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="Продолжительность игры (в секундах)")
    map_name = models.CharField(max_length=100, blank=True, null=True, help_text="Название карты")
    rounds_played = models.PositiveIntegerField(null=True, blank=True, help_text="Количество сыгранных раундов")
    game_mode = models.CharField(max_length=150, blank=True, null=True, help_text="Режим игры")
    is_ranked = models.BooleanField(blank=True, null=True, help_text="Является ли матч ранговым")

    class Meta:
        ordering = ["-match_timestamp"]

    def __str__(self):
        mode = f"({self.game_mode.split('/')[-1].replace('РежимИгры', '')})" if self.game_mode else ""
        timestamp_str = self.match_timestamp.strftime('%Y-%m-%d %H:%M') if self.match_timestamp else "Нет временного штампа"
        return f"Матч {self.id or self.game_match_id}{mode}, временной штамп {timestamp_str}"

class PlayerMatchStats(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="match_stats")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="match_stats")
    won_match = models.BooleanField(default=False, help_text="Выиграл ли игрок этот матч?")

    # Основные показатели
    kills = models.PositiveIntegerField(default=0)
    deaths = models.PositiveIntegerField(default=0)
    assists = models.PositiveIntegerField(default=0)
    kda = models.FloatField(default=0.0)

    # Умения
    skills_used = models.PositiveIntegerField(default=0, help_text="Общее кол-во примененных умений (кроме ультимейтов)")
    ultimates_used = models.PositiveIntegerField(default=0, help_text="Кол-во примененных ультимейтов")

    # Время
    time_alive_seconds = models.PositiveIntegerField(default=0, help_text="Общее время жизни в матче в секундах")

    # Цели (бомба)
    bomb_plants = models.PositiveIntegerField(default=0, help_text="Сколько раз установил бомбу")
    bomb_defuses = models.PositiveIntegerField(default=0, help_text="Сколько раз обезвредил бомбу")

    # Точность
    headshots = models.PositiveIntegerField(default=0)
    bodyshots = models.PositiveIntegerField(default=0)
    legshots = models.PositiveIntegerField(default=0)
    total_shots_hitted = models.PositiveIntegerField(default=0, help_text="Всего выстрелов попали")
    total_shots_fired = models.PositiveIntegerField(default=0, help_text="Всего выстрелов сделано")
    headshot_rate = models.FloatField(default=0.0, help_text="Процент выстрелов в голову от общих попаданий")

    # Оружие
    primary_weapon_used = models.CharField(max_length=100, blank=True, help_text="Основное/самое результативное оружие")

    # Броня
    armor_lvl1_purchases = models.PositiveIntegerField(default=0, help_text="Сколько раз купил броню 1 ур.")
    armor_lvl2_purchases = models.PositiveIntegerField(default=0, help_text="Сколько раз купил броню 2 ур.")

    class Meta:
        # Гарантируем, что для одного игрока в одном матче есть только одна запись статистики
        unique_together = ("player", "match")

        # Сортируем по умолчанию по дате матча (сначала новые) для удобства просмотра истории
        ordering = ["-match__match_timestamp"]
        verbose_name = "Статистика игрока за матч"
        verbose_name_plural = "Статистика игроков за матчи"

    def __str__(self):
        return f"{self.player.username} в матче {self.match.id} ({'Победа' if self.won_match else 'Проигрыш'})"
