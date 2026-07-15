from django.contrib import admin
from .models import Attendance, Meeting, ParticipationTracking

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['member', 'meeting_date', 'attended', 'meeting_type']
    list_filter = ['attended', 'meeting_type']
    search_fields = ['member__full_name']

@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ['title', 'group', 'meeting_date', 'is_completed']
    list_filter = ['meeting_type', 'is_completed']
    search_fields = ['title', 'agenda']

@admin.register(ParticipationTracking)
class ParticipationTrackingAdmin(admin.ModelAdmin):
    list_display = ['member', 'meeting_date', 'participated', 'points']
    list_filter = ['participated']
    search_fields = ['member__full_name']