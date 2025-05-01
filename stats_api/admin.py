from django.contrib import admin
from .models import Player, Match, PlayerMatchStats


class PlayerMatchStatsAdmin(admin.ModelAdmin):
    list_display = ('player', 'match', 'won_match', 'kills', 'deaths', 'assists', 'kda') # Отображаемые колонки
    list_filter = ('player', 'match__match_timestamp', 'won_match') # Фильтры
    search_fields = ('player__username', 'match__game_match_id') # Поиск по имени игрока или ID матча
    readonly_fields = ('kda',)

admin.site.register(Player)
admin.site.register(Match)
admin.site.register(PlayerMatchStats, PlayerMatchStatsAdmin)

