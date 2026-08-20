from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, export_views

router = DefaultRouter()
router.register('groups', views.StudentGroupViewSet, basename='studentgroup')
router.register('constraints', views.PeerConstraintViewSet, basename='peerconstraint')
router.register('assignments', views.GroupAssignmentViewSet, basename='groupassignment')

urlpatterns = [
    path('', include(router.urls)),
    path('classroom/<int:classroom_id>/overview/', views.ClassroomGroupsOverviewView.as_view(), name='groups_overview'),
    path('classroom/<int:classroom_id>/seating-chart/', views.ClassroomSeatingChartView.as_view(), name='groups_seating_chart'),
    path('classroom/<int:classroom_id>/transfers/', views.ClassroomGroupTransfersView.as_view(), name='groups_transfers'),
    path('classroom/<int:classroom_id>/effectiveness/', views.ClassroomGroupEffectivenessView.as_view(), name='groups_effectiveness'),
    path('classroom/<int:classroom_id>/rebalance-suggestions/', views.ClassroomRebalanceSuggestionsView.as_view(), name='groups_rebalance_suggestions'),

    # Group work (assignment) analytics + performance-based reassignment.
    path('assignments/classroom/<int:classroom_id>/analytics/',
         views.GroupWorkAnalyticsView.as_view(), name='group_work_analytics'),
    path('assignments/classroom/<int:classroom_id>/reassignment-suggestions/',
         views.GroupAssignmentReassignmentView.as_view(), name='group_assignment_reassignment'),

    # Exports — PDF/Excel only, per the platform's export policy.
    path('export/classroom/<int:classroom_id>/summary/pdf/',
         export_views.GroupsSummaryPDFView.as_view(), name='groups_summary_pdf'),
    path('export/classroom/<int:classroom_id>/summary/excel/',
         export_views.GroupsSummaryExcelView.as_view(), name='groups_summary_excel'),
    path('export/classroom/<int:classroom_id>/roster/pdf/',
         export_views.GroupsRosterPDFView.as_view(), name='groups_roster_pdf'),
    path('export/classroom/<int:classroom_id>/roster/excel/',
         export_views.GroupsRosterExcelView.as_view(), name='groups_roster_excel'),

    # Group work analytics exports — PDF/Excel summary, plus a raw CSV of
    # every recorded mark for spreadsheet-side analysis.
    path('export/classroom/<int:classroom_id>/assignments/analytics/pdf/',
         export_views.GroupWorkAnalyticsPDFView.as_view(), name='group_work_analytics_pdf'),
    path('export/classroom/<int:classroom_id>/assignments/analytics/excel/',
         export_views.GroupWorkAnalyticsExcelView.as_view(), name='group_work_analytics_excel'),
    path('export/classroom/<int:classroom_id>/assignments/marks/csv/',
         export_views.GroupAssignmentMarksCSVView.as_view(), name='group_assignment_marks_csv'),
]
