from django.shortcuts import render
from rest_framework import viewsets
from .models import Player
from .serializers import PlayerSerializer

class PlayerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Эндпоинт API который отображает всех пользователей.
    """
    queryset = Player.objects.all().order_by('username')
    serializer_class = PlayerSerializer
