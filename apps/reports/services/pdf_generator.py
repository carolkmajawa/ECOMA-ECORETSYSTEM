# apps/reports/services/pdf_generator.py

import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

class PDFReportGenerator:
    """Generate PDF reports"""
    
    def __init__(self, report_data, group_name):
        self.data = report_data
        self.group_name = group_name
        self.styles = getSampleStyleSheet()
        self.setup_styles()
    
    def setup_styles(self):
        """Setup custom styles"""
        # Title style
        self.title_style = ParagraphStyle(
            'ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=30,
            textColor=colors.HexColor('#0B6B80'),
        )
        
        # Section heading style
        self.section_style = ParagraphStyle(
            'SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            alignment=TA_LEFT,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.HexColor('#C50982'),
        )
        
        # Sub section heading
        self.sub_heading_style = ParagraphStyle(
            'SubHeading',
            parent=self.styles['Heading3'],
            fontSize=13,
            alignment=TA_LEFT,
            spaceAfter=8,
            textColor=colors.HexColor('#0B6B80'),
        )
        
        # Body text
        self.body_style = ParagraphStyle(
            'BodyText',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT,
            spaceAfter=4,
        )
        
        # Footer style
        self.footer_style = ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.grey,
        )
    
    def generate(self, output_filename):
        """Generate PDF report"""
        doc = SimpleDocTemplate(
            output_filename,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )
        
        story = []
        
        story.extend(self.create_header())
        story.extend(self.create_group_info())
        story.extend(self.create_cycle_info())
        story.extend(self.create_member_summary())
        story.extend(self.create_contribution_summary())
        story.extend(self.create_loan_summary())
        story.extend(self.create_transaction_summary())
        story.extend(self.create_attendance_summary())
        story.extend(self.create_member_performance())
        story.extend(self.create_financial_summary())
        story.extend(self.create_footer())
        
        doc.build(story)
        return output_filename
    
    def create_header(self):
        """Create report header"""
        story = []
        title = f"{self.group_name} - Cycle Report"
        story.append(Paragraph(title, self.title_style))
        
        date_range = f"Report Period: {self.data['metadata']['date_range']['start'][:10]} to {self.data['metadata']['date_range']['end'][:10]}"
        story.append(Paragraph(date_range, self.body_style))
        
        generated = f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}"
        story.append(Paragraph(generated, self.body_style))
        
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("="*80, self.body_style))
        story.append(Spacer(1, 0.2*inch))
        return story
    
    def create_group_info(self):
        """Create group information section"""
        group = self.data.get('group_info', {})
        story = []
        story.append(Paragraph("GROUP INFORMATION", self.section_style))
        
        # Ensure group is a dict
        if not isinstance(group, dict):
            group = {}
        
        data = [
            ['Group Name:', group.get('name', 'N/A')],
            ['Group Code:', group.get('code', 'N/A')],
            ['Total Members:', str(group.get('total_members', 0))],
            ['Active Members:', str(group.get('active_members', 0))],
            ['Address:', group.get('address', 'N/A')],
            ['Created:', group.get('created_at', 'N/A')[:10] if group.get('created_at') else 'N/A'],
        ]
        
        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f9ff')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 0.2*inch))
        return story
    
    def create_cycle_info(self):
        """Create cycle information section"""
        cycle = self.data.get('cycle_info', {})
        story = []
        story.append(Paragraph("CYCLE INFORMATION", self.section_style))
        
        # Ensure cycle is a dict
        if not isinstance(cycle, dict):
            cycle = {}
        
        data = [
            ['Start Date:', cycle.get('start_date', 'N/A')[:10] if cycle.get('start_date') else 'N/A'],
            ['End Date:', cycle.get('end_date', 'N/A')[:10] if cycle.get('end_date') else 'N/A'],
            ['Status:', 'Active' if cycle.get('is_active') else 'Inactive'],
            ['Duration:', f"{cycle.get('duration_months', 0)} months"],
        ]
        
        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0fdf4')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 0.2*inch))
        return story
    
    def create_member_summary(self):
        """Create member summary section"""
        members = self.data.get('members', [])
        story = []
        story.append(Paragraph("MEMBER SUMMARY", self.section_style))
        
        # Ensure members is a list
        if not isinstance(members, list):
            members = []
        
        story.append(Paragraph(f"Total Members: {len(members)}", self.body_style))
        story.append(Spacer(1, 0.1*inch))
        
        if members and len(members) > 0:
            # Create member table
            data = [['#', 'Name', 'Phone', 'Gender', 'Status']]
            
            # Only show first 30 members to avoid huge PDFs
            display_members = members[:30] if len(members) > 30 else members
            
            for idx, member in enumerate(display_members, 1):
                # Safely get values with defaults
                if isinstance(member, dict):
                    full_name = member.get('full_name', 'N/A')
                    phone = member.get('phone_number', 'N/A')
                    gender = member.get('gender', 'N/A')
                    is_active = member.get('is_active', False)
                else:
                    full_name = str(member)
                    phone = 'N/A'
                    gender = 'N/A'
                    is_active = False
                
                data.append([
                    str(idx),
                    full_name,
                    phone,
                    gender,
                    'Active' if is_active else 'Inactive',
                ])
            
            if len(members) > 30:
                data.append(['', f'... and {len(members) - 30} more members', '', '', ''])
            
            table = Table(data, colWidths=[0.5*inch, 2.5*inch, 1.5*inch, 0.8*inch, 0.8*inch])
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B6B80')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('PADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(table)
        else:
            story.append(Paragraph("No members found.", self.body_style))
        
        story.append(Spacer(1, 0.2*inch))
        return story
    
    def create_contribution_summary(self):
        """Create contribution summary section"""
        contrib = self.data.get('contributions', {})
        story = []
        story.append(Paragraph("CONTRIBUTION SUMMARY", self.section_style))
        
        # Ensure contrib is a dict
        if not isinstance(contrib, dict):
            contrib = {}
        
        data = [
            ['Total Savings:', f"MK {contrib.get('total_savings', 0):,.2f}"],
            ['Total Loans:', f"MK {contrib.get('total_loans', 0):,.2f}"],
            ['Total Penalties:', f"MK {contrib.get('total_penalties', 0):,.2f}"],
            ['Total Interest:', f"MK {contrib.get('total_interest', 0):,.2f}"],
            ['Net Contribution:', f"MK {(contrib.get('total_savings', 0) + contrib.get('total_loans', 0)):,.2f}"],
        ]
        
        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0fdf4')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 0.2*inch))
        return story
    
    def create_loan_summary(self):
        """Create loan summary section"""
        loans = self.data.get('loans', {})
        story = []
        story.append(Paragraph("LOAN SUMMARY", self.section_style))
        
        # Ensure loans is a dict
        if not isinstance(loans, dict):
            loans = {}
        
        data = [
            ['Total Loans:', str(loans.get('total_loans', 0))],
            ['Total Amount:', f"MK {loans.get('total_amount', 0):,.2f}"],
            ['Total Repaid:', f"MK {loans.get('total_repaid', 0):,.2f}"],
            ['Total Balance:', f"MK {loans.get('total_balance', 0):,.2f}"],
            ['Active Loans:', str(loans.get('active_loans', 0))],
            ['Approved Loans:', str(loans.get('approved_loans', 0))],
            ['Completed Loans:', str(loans.get('completed_loans', 0))],
            ['Defaulted Loans:', str(loans.get('defaulted_loans', 0))],
            ['Pending Loans:', str(loans.get('pending_loans', 0))],
            ['Repayment Rate:', f"{loans.get('repayment_rate', 0):.1f}%"],
        ]
        
        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#fef3c7')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 0.2*inch))
        return story
    
    def create_transaction_summary(self):
        """Create transaction summary section"""
        transactions = self.data.get('transactions', {})
        story = []
        story.append(Paragraph("TRANSACTION SUMMARY", self.section_style))
        
        # Ensure transactions is a dict
        if not isinstance(transactions, dict):
            transactions = {}
        
        data = [
            ['Total Entries:', str(transactions.get('total_entries', 0))],
            ['Total Debit:', f"MK {transactions.get('total_debit', 0):,.2f}"],
            ['Total Credit:', f"MK {transactions.get('total_credit', 0):,.2f}"],
            ['Net Balance:', f"MK {transactions.get('net_balance', 0):,.2f}"],
        ]
        
        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#dbeafe')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 0.2*inch))
        return story
    
    def create_attendance_summary(self):
        """Create attendance summary section"""
        attendance = self.data.get('attendance', {})
        story = []
        story.append(Paragraph("ATTENDANCE SUMMARY", self.section_style))
        
        # Ensure attendance is a dict
        if not isinstance(attendance, dict):
            attendance = {}
        
        data = [
            ['Total Meetings:', str(attendance.get('total_meetings', 0))],
            ['Present:', str(attendance.get('present', 0))],
            ['Absent:', str(attendance.get('absent', 0))],
            ['Excused:', str(attendance.get('excused', 0))],
            ['Attendance Rate:', f"{attendance.get('attendance_rate', 0):.1f}%"],
        ]
        
        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0fdf4')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 0.2*inch))
        return story
    
    def create_member_performance(self):
        """Create member performance section"""
        performance = self.data.get('performance', [])
        story = []
        story.append(Paragraph("MEMBER PERFORMANCE", self.section_style))
        
        # Ensure performance is a list
        if not isinstance(performance, list):
            performance = []
        
        if performance and len(performance) > 0:
            # Top 10 performers
            top_performers = performance[:10] if len(performance) > 10 else performance
            
            data = [['Rank', 'Member', 'Savings', 'Loans', 'Attendance', 'Rating']]
            for idx, member in enumerate(top_performers, 1):
                if isinstance(member, dict):
                    full_name = member.get('full_name', 'N/A')
                    total_savings = member.get('total_savings', 0)
                    total_loans = member.get('total_loans_taken', 0)
                    attendance_rate = member.get('attendance_rate', 0)
                    performance_rating = member.get('performance_rating', 0)
                else:
                    full_name = str(member)
                    total_savings = 0
                    total_loans = 0
                    attendance_rate = 0
                    performance_rating = 0
                
                data.append([
                    str(idx),
                    full_name,
                    f"MK {total_savings:,.0f}",
                    f"MK {total_loans:,.0f}",
                    f"{attendance_rate:.0f}%",
                    f"{performance_rating:.0f}%",
                ])
            
            table = Table(data, colWidths=[0.5*inch, 1.5*inch, 1*inch, 1*inch, 0.8*inch, 0.8*inch])
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B6B80')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('PADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(table)
        else:
            story.append(Paragraph("No performance data available.", self.body_style))
        
        story.append(Spacer(1, 0.2*inch))
        return story
    
    def create_financial_summary(self):
        """Create financial summary section"""
        financial = self.data.get('financial_summary', {})
        story = []
        story.append(Paragraph("FINANCIAL SUMMARY", self.section_style))
        
        # Ensure financial is a dict
        if not isinstance(financial, dict):
            financial = {}
        
        data = [
            ['Total Savings:', f"MK {financial.get('total_savings', 0):,.2f}"],
            ['Total Loans Disbursed:', f"MK {financial.get('total_loans_disbursed', 0):,.2f}"],
            ['Total Repaid:', f"MK {financial.get('total_repaid', 0):,.2f}"],
            ['Outstanding Balance:', f"MK {financial.get('outstanding_balance', 0):,.2f}"],
            ['Total Debit:', f"MK {financial.get('total_transactions_debit', 0):,.2f}"],
            ['Total Credit:', f"MK {financial.get('total_transactions_credit', 0):,.2f}"],
            ['Net Transactions:', f"MK {financial.get('net_transactions', 0):,.2f}"],
            ['Total Contributions:', f"MK {financial.get('total_contributions', 0):,.2f}"],
        ]
        
        table = Table(data, colWidths=[2.5*inch, 3.5*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3e8ff')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 0.2*inch))
        return story
    
    def create_footer(self):
        """Create report footer"""
        return [
            Spacer(1, 0.5*inch),
            Paragraph(
                f"<font size=8 color=grey>Generated by ECORET System • {datetime.now().strftime('%B %d, %Y at %H:%M')}</font>",
                self.footer_style
            ),
            Paragraph(
                f"<font size=8 color=grey>© {datetime.now().year} ECORET Microcredit Agency. All rights reserved.</font>",
                self.footer_style
            ),
        ]