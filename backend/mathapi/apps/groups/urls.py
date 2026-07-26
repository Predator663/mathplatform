from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, export_views

router = DefaultRouter()
router.register('groups', views.StudentGroupViewSet, basename='studentgroup')
router.register('constraints', views.PeerConstraintViewSet, basename='peerconstraint')

urlpatterns = [
    path('', include(router.urls)),
    path('classroom/<int:classroom_id>/overview/', views.ClassroomGroupsOverviewView.as_view(), name='groups_overview'),
    path('classroom/<int:classroom_id>/transfers/', views.ClassroomGroupTransfersView.as_view(), name='groups_transfers'),
    path('classroom/<int:classroom_id>/effectiveness/', views.ClassroomGroupEffectivenessView.as_view(), name='groups_effectiveness'),
    path('classroom/<int:classroom_id>/rebalance-suggestions/', views.ClassroomRebalanceSuggestionsView.as_view(), name='groups_rebalance_suggestions'),

    # Exports — PDF/Excel only, per the platform's export policy.
    path('export/classroom/<int:classroom_id>/summary/pdf/',
         export_views.GroupsSummaryPDFView.as_view(), name='groups_summary_pdf'),
    path('export/classroom/<int:classroom_id>/summary/excel/',
         export_views.GroupsSummaryExcelView.as_view(), name='groups_summary_excel'),
    path('export/classroom/<int:classroom_id>/roster/pdf/',
         export_views.GroupsRosterPDFView.as_view(), name='groups_roster_pdf'),
    path('export/classroom/<int:classroom_id>/roster/excel/',
         export_views.GroupsRosterExcelView.as_view(), name='groups_roster_excel'),
]
