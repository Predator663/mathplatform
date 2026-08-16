from django.contrib import admin
from .models import Tournament, TournamentEntry, Challenge, EntryResult


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ['title', 'mode', 'classroom', 'exam', 'status', 'registration_deadline']
    list_filter = ['mode', 'status', 'classroom']
    search_fields = ['title', 'codename']


@admin.register(TournamentEntry)
class TournamentEntryAdmin(admin.ModelAdmin):
    list_display = ['tournament', 'display_name', 'seed_average', 'withdrawn']
    list_filter = ['tournament', 'withdrawn']


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ['tournament', 'label', 'status', 'winner', 'is_tie']
    list_filter = ['status', 'tournament']


@admin.register(EntryResult)
class EntryResultAdmin(admin.ModelAdmin):
    list_display = ['entry', 'rank', 'score_percentage', 'is_champion', 'is_rising_star']
    list_filter = ['is_champion', 'is_rising_star']
