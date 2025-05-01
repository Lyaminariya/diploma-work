from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Player(models.Model):
    username = models.CharField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username

class Match(models.Model):
    game_match_id = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    match_timestamp = models.DateTimeField(db_index=True, help_text="Дата и время начала игры")
    duration_secons = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-match_timestamp']

    def __str__(self):
        return f"Match {self.id or self.game_match_id} at {self.match_timestamp.strftime('%Y-%m-%d %H:%M')}"

class PlayerMatchStats(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='match_stats')
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='match_stats')
    won_match = models.BooleanField(default=False, help_text='Выиграл ли игрок этот матч?')

    # Основные показатели
    kills = models.PositiveIntegerField(default=0)
    deaths = models.PositiveIntegerField(default=0)
    assists = models.PositiveIntegerField(default=0)

    # Умения
    skills_used = models.PositiveIntegerField(default=0, help_text='Общее кол-во примененных умений (кроме ультимейтов)')
    ultimates_used = models.PositiveIntegerField(default=0, help_text='Кол-во примененных ультимейтов')

    # Время
    time_alive_seconds = models.PositiveIntegerField(default=0, help_text='Общее время жизни в матче в секундах')

    # Цели (бомба)
    bomb_plants = models.PositiveIntegerField(default=0, help_text='Сколько раз установил бомбу')
    bomb_defuses = models.PositiveIntegerField(default=0, help_text='Сколько раз обезвредил бомбу')

    # Точность
    headshots = models.PositiveIntegerField(default=0)
    bodyshots = models.PositiveIntegerField(default=0)
    legshots = models.PositiveIntegerField(default=0)
    total_shots_hitted = models.PositiveIntegerField(default=0, help_text='Всего выстрелов попало')
    total_shots_fired = models.PositiveIntegerField(default=0, help_text='Всего выстрелов сделано')

    # Оружие
    primary_weapon_used = models.CharField(max_length=100, blank=True, help_text='Основное/самое результативное оружие')

    # Броня
    armor_lvl1_purchases = models.PositiveIntegerField(default=0, help_text='Сколько раз купил броню 1 ур.')
    armor_lvl2_purchases = models.PositiveIntegerField(default=0, help_text='Сколько раз купил броню 2 ур.')

    class Meta:
        # Гарантируем, что для одного игрока в одном матче есть только одна запись статистики
        unique_together = ('player', 'match')
        # Сортируем по умолчанию по дате матча (сначала новые) для удобства просмотра истории
        ordering = ['-match__match_timestamp']
        verbose_name = 'Статистика игрока за матч'
        verbose_name_plural = 'Статистика игроков за матчи'

    def __str__(self):
        return f"{self.player.username} in Match {self.match.id} ({'Win' if self.won_match else 'Lose'})"

    @property
    def kda(self):
        if self.deaths > 0:
            return round((self.kills + self.assists) / self.deaths, 2)
        return self.kills + self.assists

    @property
    def headshot_rate(self):
        if self.total_shots_fired > 0:
            return round((self.headshots / self.total_shots_fired) * 100, 1)
        return 0.0
