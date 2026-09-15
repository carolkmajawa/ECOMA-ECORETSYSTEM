import os
import tempfile
from datetime import datetime
from django.utils import timezone
from django.http import FileResponse, request
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request as DRFRequest
from django.core.files import File
from django.test import RequestFactory

from .models import Report
from .serializers import ReportSerializer, ReportGenerateSerializer
from .services.report_generator import ReportDataCollector
from .services.pdf_generator import PDFReportGenerator
from apps.groups.models import Group, GroupMember

class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        member_group_ids = GroupMember.objects.filter(
            user=user, 
            is_active=True
        ).values_list('group_id', flat=True)
        
        chairman_group_ids = Group.objects.filter(
            chairman=user
        ).values_list('id', flat=True)
        
        group_ids = set(list(member_group_ids) + list(chairman_group_ids))
        
        if user.role == 'admin':
            return Report.objects.all().order_by('-created_at')
        
        return Report.objects.filter(group_id__in=group_ids).order_by('-created_at')
    
    @action(detail=False, methods=['post'], url_path='generate')
    def generate_report(self, request):
        """Generate a new report with all fields"""
        try:
            serializer = ReportGenerateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            validated_data = serializer.validated_data
            group_id = validated_data['group_id']
            period = validated_data['period']
            start_date = validated_data.get('start_date')
            end_date = validated_data.get('end_date')
            include_members = validated_data.get('include_members', [])
            include_sections = validated_data.get('include_sections', [])
            report_format = validated_data.get('format', 'pdf')

            try:
                group = Group.objects.get(id=group_id)
            except Group.DoesNotExist:
                return Response({'error': 'Group not found'}, status=status.HTTP_404_NOT_FOUND)

            is_member = GroupMember.objects.filter(
                group=group, user=request.user, is_active=True
            ).exists()
            is_chairman = group.chairman == request.user if hasattr(group, 'chairman') else False
            is_admin = request.user.role == 'admin'

            if not (is_member or is_chairman or is_admin):
                return Response(
                    {'error': 'You are not a member of this group'},
                    status=status.HTTP_403_FORBIDDEN
                )

            if not start_date or not end_date:
                start_date, end_date = self.calculate_date_range(period, group, request)

            report = Report.objects.create(
                group=group,
                report_type='full_cycle',
                format=report_format,
                generated_by=request.user,
                start_date=start_date,
                end_date=end_date,
                include_members=include_members,
                include_sections=include_sections,
                status='generating'
            )

            try:
                self._process_report(report)
            except Exception as e:
                import traceback
                traceback.print_exc()
                return Response({
                    'message': 'Report created but generation failed',
                    'report_id': str(report.id),
                    'status': 'failed',
                    'error': str(e),
                }, status=status.HTTP_200_OK)

            return Response({
                'message': 'Report generated successfully',
                'report_id': str(report.id),
                'status': report.status,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Failed to start report generation: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def calculate_date_range(self, period, group, request):
        """Calculate start and end dates based on period"""
        now = timezone.now()
        
        if period == 'this_cycle':
            if group.cycle_start_date and group.cycle_end_date:
                return group.cycle_start_date, group.cycle_end_date
            return now - timezone.timedelta(days=30), now
            
        elif period == 'last_cycle':
            return now - timezone.timedelta(days=60), now - timezone.timedelta(days=30)
            
        elif period == 'this_month':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start, now
            
        elif period == 'last_month':
            start = (now.replace(day=1) - timezone.timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timezone.timedelta(microseconds=1)
            return start, end
            
        elif period == 'custom':
            return None, None
            
        elif period == 'all_time':
            return group.created_at or now - timezone.timedelta(days=365), now
            
        return now - timezone.timedelta(days=30), now
    
    @action(detail=True, methods=['get'], url_path='download')
    def download_report(self, request, pk=None):
        """Download a generated report"""
        report = self.get_object()

        if report.status != 'completed':
            return Response(
                {'error': 'Report is not ready for download'},
                status=status.HTTP_400_BAD_REQUEST
            )

        file_field = report.get_file()
        if not file_field or not file_field.name:
            return Response(
                {'error': 'Report file not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        report.download_count += 1
        report.save()

        return FileResponse(
            file_field.open('rb'),
            as_attachment=True,
            filename=os.path.basename(file_field.name)
        )
    
    @action(detail=False, methods=['get'], url_path='pending')
    def pending_requests(self, request):
        """Get pending report generation requests"""
        user = request.user
        
        member_group_ids = GroupMember.objects.filter(
            user=user, 
            is_active=True
        ).values_list('group_id', flat=True)
        
        chairman_group_ids = Group.objects.filter(
            chairman=user
        ).values_list('id', flat=True)
        
        group_ids = set(list(member_group_ids) + list(chairman_group_ids))
        
        pending = Report.objects.filter(
            group_id__in=group_ids,
            status__in=['pending', 'generating']
        )
        serializer = self.get_serializer(pending, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='regenerate')
    def regenerate_report(self, request, pk=None):
        """Regenerate a report with updated data"""
        report = self.get_object()
        
        user = request.user
        is_member = GroupMember.objects.filter(
            group=report.group, 
            user=user, 
            is_active=True
        ).exists()
        is_chairman = report.group.chairman == user if hasattr(report.group, 'chairman') else False
        is_admin = user.role == 'admin'
        
        if not (is_member or is_chairman or is_admin):
            return Response(
                {'error': 'You do not have permission to regenerate this report'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if report.status == 'generating':
            return Response(
                {'error': 'Report is already being generated'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        report.status = 'pending'
        report.save()
        
        data = {
            'group_id': str(report.group_id),
            'period': 'this_cycle',
            'start_date': report.start_date.isoformat(),
            'end_date': report.end_date.isoformat(),
            'include_members': report.include_members,
            'include_sections': report.include_sections,
            'format': report.format,
        }
        
        factory = RequestFactory()
        new_request = factory.post(
            '/api/reports/generate/', 
            data, 
            content_type='application/json'
        )
        
        new_request.user = request.user
        new_request.auth = getattr(request, 'auth', None)
        new_request.successful_authenticator = getattr(request, 'successful_authenticator', None)
        new_request._request = request._request if hasattr(request, '_request') else request
        
        new_request.data = data
        new_request._full_data = data
        
        return self.generate_report(new_request)

    @action(detail=True, methods=['get'], url_path='status')
    def report_status(self, request, pk=None):
        """Check report generation status"""
        report = self.get_object()
    
        if report.status == 'completed':
            return Response({
                'status': 'completed',
                'report': ReportSerializer(report, context={'request': request}).data
            })
    
        if report.status == 'generating':
            try:
                self._process_report(report)
                return Response({
                    'status': 'completed',
                    'report': ReportSerializer(report, context={'request': request}).data
                })
            except Exception as e:
                report.status = 'failed'
                report.save()
                return Response({
                    'status': 'failed',
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
        if report.status == 'failed':
            return Response({
                'status': 'failed',
                'error': 'Report generation failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
        return Response({
            'status': report.status
        })
    
    def _process_report(self, report):
        """Process the report generation"""
        try:
            collector = ReportDataCollector(
                report.group,
                report.start_date,
                report.end_date,
                report.include_members,
                report.include_sections
            )
            report_data = collector.collect_all()
            report.report_data = report_data

            if report.format in ('pdf', 'both'):
                pdf_generator = PDFReportGenerator(report_data, report.group.group_name)
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                    pdf_generator.generate(tmp_file.name)
                    filename = f"cycle_report_{report.group.group_name}_{report.start_date.date()}.pdf"
                    report.pdf_file.save(filename, File(open(tmp_file.name, 'rb')))
                os.unlink(tmp_file.name)

            if report.format in ('excel', 'both'):
                from .services.excel_generator import ExcelReportGenerator
                excel_generator = ExcelReportGenerator(report_data, report.group.group_name)
                with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
                    excel_generator.generate(tmp_file.name)
                    filename = f"cycle_report_{report.group.group_name}_{report.start_date.date()}.xlsx"
                    report.excel_file.save(filename, File(open(tmp_file.name, 'rb')))
                os.unlink(tmp_file.name)

            report.status = 'completed'
            report.completed_at = timezone.now()
            report.file_size = (report.pdf_file.size if report.pdf_file else 0) + \
                                (report.excel_file.size if report.excel_file else 0)
            report.save()

        except Exception as e:
            report.status = 'failed'
            report.save()
            raise e

    @action(detail=True, methods=['delete'], url_path='delete')
    def delete_report(self, request, pk=None):
        """Delete a report"""
        report = self.get_object()
    
        user = request.user
        is_member = GroupMember.objects.filter(
            group=report.group, 
            user=user, 
            is_active=True
        ).exists()
        is_chairman = report.group.chairman == user if hasattr(report.group, 'chairman') else False
        is_admin = user.role == 'admin'
        
        if not (is_member or is_chairman or is_admin):
            return Response(
                {'error': 'You do not have permission to delete this report'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        report.delete()
        
        return Response({
            'message': 'Report deleted successfully'
        }, status=status.HTTP_200_OK)    