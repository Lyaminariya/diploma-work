from django.db import models

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