from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PlayerViewSet,
    MatchViewSet,
    PlayerMatchStatsViewSet,
    DBSCANAnalysisView,
    CSVImportView,
    AvailableGamesView,
)

router = DefaultRouter()

router.register(r'players', PlayerViewSet, basename='player')
router.register(r'matches', MatchViewSet, basename='match')

router.register(r'player-match-stats', PlayerMatchStatsViewSet, basename='playermatchstats')

urlpatterns = [
    path('', include(router.urls)),
    path('stats/dbscan-analysis/', DBSCANAnalysisView.as_view(), name='dbscan_analysis'),
    path('import-csv/', CSVImportView.as_view(), name='csv_import'),
    path('available-games/', AvailableGamesView.as_view(), name='available_games'),
]