from django.contrib import admin
from .models import LeagueSeason, LeagueGroup, LeagueMembership, PromotionEvent


class LeagueGroupInline(admin.TabularInline):
    model = LeagueGroup
    extra = 0


@admin.register(LeagueSeason)
class LeagueSeasonAdmin(admin.ModelAdmin):
    list_display = ['title', 'classroom', 'baseline_exam', 'interval_mode', 'promotion_mode', 'status', 'created_at']
    list_filter = ['status', 'interval_mode', 'promotion_mode']
    search_fields = ['title', 'classroom__name']
    inlines = [LeagueGroupInline]


@admin.register(LeagueGroup)
class LeagueGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'season', 'min_mark', 'max_mark', 'order']
    list_filter = ['season']


@admin.register(LeagueMembership)
class LeagueMembershipAdmin(admin.ModelAdmin):
    list_display = ['student', 'season', 'group', 'latest_score', 'is_promotion_pending']
    list_filter = ['season', 'group', 'is_promotion_pending']
    search_fields = ['student__user__first_name', 'student__user__last_name']


@admin.register(PromotionEvent)
class PromotionEventAdmin(admin.ModelAdmin):
    list_display = ['student', 'season', 'from_group', 'to_group', 'status', 'created_at']
    list_filter = ['season', 'status']
