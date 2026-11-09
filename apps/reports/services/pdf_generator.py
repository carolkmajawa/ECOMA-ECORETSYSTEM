# import os
from datetime import datetime
from xml.sax.saxutils import escape
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
        self.title_style = ParagraphStyle(
            'ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=30,
            textColor=colors.HexColor('#0B6B80'),
        )
        
        self.section_style = ParagraphStyle(
            'SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            alignment=TA_LEFT,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.HexColor('#C50982'),
        )
        
        self.sub_heading_style = ParagraphStyle(
            'SubHeading',
            parent=self.styles['Heading3'],
            fontSize=13,
            alignment=TA_LEFT,
            spaceAfter=8,
            textColor=colors.HexColor('#0B6B80'),
        )
        
        self.body_style = ParagraphStyle(
            'BodyText',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT,
            spaceAfter=4,
        )

        # Small wrapping style for table cells (names, addresses, IDs)
        self.cell_style = ParagraphStyle(
            'TableCell',
            parent=self.styles['Normal'],
            fontSize=8,
            leading=10,
        )
        
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

        if not isinstance(group, dict):
            group = {}

        # Gender counts are calculated by the data collector for the whole group
        male_count = group.get('male_count', 0)
        female_count = group.get('female_count', 0)
        other_count = group.get('other_count', 0)
        unspecified_count = group.get('unspecified_count', 0)
        
        data = [
            ['Group Name:', group.get('name', 'N/A')],
            ['Group Code:', group.get('code', 'N/A')],
            ['Total Members:', str(group.get('total_members', 0))],
            ['Active Members:', str(group.get('active_members', 0))],
            ['Male Members:', str(male_count)],
            ['Female Members:', str(female_count)],
        ]

        # Only shown when someone falls outside Male/Female, so the numbers add up
        if other_count:
            data.append(['Other Gender:', str(other_count)])
        if unspecified_count:
            data.append(['Gender Not Specified:', str(unspecified_count)])

        data.extend([
            ['Address:', group.get('address', 'N/A')],
            ['Created:', group.get('created_at', 'N/A')[:10] if group.get('created_at') else 'N/A'],
        ])
        
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
        """Create member summary section (includes each member's National ID)"""
        members = self.data.get('members', [])
        story = []
        story.append(Paragraph("MEMBER SUMMARY", self.section_style))
        
        if not isinstance(members, list):
            members = []
        
        story.append(Paragraph(f"Total Members: {len(members)}", self.body_style))
        story.append(Spacer(1, 0.1*inch))
        
        if members:
            def cell(value):
                # Paragraph cells wrap long names/addresses instead of overflowing
                return Paragraph(escape(str(value)), self.cell_style)

            data = [['#', 'National ID', 'Name', 'Phone', 'Gender', 'Address', 'Status']]
            
            display_members = members[:30]
            
            for idx, member in enumerate(display_members, 1):
                if isinstance(member, dict):
                    national_id = member.get('national_id') or 'N/A'
                    full_name = member.get('full_name', 'N/A')
                    phone = member.get('phone_number', 'N/A')
                    gender = member.get('gender_label') or member.get('gender') or 'N/A'
                    address = member.get('address', 'N/A')
                    is_active = member.get('is_active', False)
                else:
                    national_id = 'N/A'
                    full_name = str(member)
                    phone = 'N/A'
                    gender = 'N/A'
                    address = 'N/A'
                    is_active = False
                
                data.append([
                    str(idx),
                    cell(national_id),
                    cell(full_name),
                    cell(phone),
                    cell(gender),
                    cell(address),
                    'Active' if is_active else 'Inactive',
                ])
            
            if len(members) > 30:
                data.append(['', f'... and {len(members) - 30} more members', '', '', '', '', ''])
            
            # 7 columns, 6.25 inches in total (fits the A4 page between the margins)
            col_widths = [0.3*inch, 1.05*inch, 1.35*inch, 1.0*inch, 0.55*inch, 1.4*inch, 0.6*inch]
            table = Table(data, colWidths=col_widths, repeatRows=1)

            style = [
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0B6B80')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('PADDING', (0, 0), (-1, -1), 4),
            ]
            if len(members) > 30:
                last = len(data) - 1
                style.append(('SPAN', (1, last), (-1, last)))
            table.setStyle(TableStyle(style))
            story.append(table)
        else:
            story.append(Paragraph("No members found.", self.body_style))
        
        story.append(Spacer(1, 0.2*inch))
        return story
    
    def _money(self, value):
        try:
            return f"MK {float(value or 0):,.2f}"
        except (TypeError, ValueError):
            return "MK 0.00"

    def _count(self, value):
        try:
            return str(int(value or 0))
        except (TypeError, ValueError):
            return "0"

    def _error_story(self, data):
        """Explain why a section is empty instead of printing misleading zeros."""
        if isinstance(data, dict) and data.get('error'):
            return [
                Paragraph(
                    f"This section could not be generated: {escape(str(data['error']))}",
                    self.body_style,
                ),
                Spacer(1, 0.2*inch),
            ]
        return None

    def _summary_table(self, rows, label_bg):
        table = Table(rows, colWidths=[2.5*inch, 3.5*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor(label_bg)),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ]))
        return table

    def create_contribution_summary(self):
        """Create contribution summary section"""
        contrib = self.data.get('contributions', {})
        story = [Paragraph("CONTRIBUTION SUMMARY", self.section_style)]

        error = self._error_story(contrib)
        if error:
            return story + error
        if not isinstance(contrib, dict):
            contrib = {}

        rows = [
            ['Total Deposits:', self._money(contrib.get('total_savings'))],
            ['Total Withdrawals:', self._money(contrib.get('total_withdrawals'))],
            ['Net Savings (this period):', self._money(contrib.get('net_savings'))],
            ['Total Savings Balance (to date):', self._money(contrib.get('savings_balance'))],
            ['Social Fund Contributions:', self._money(contrib.get('total_social'))],
            ['Penalties & Fines:', self._money(contrib.get('total_penalties'))],
            ['Loan Interest Paid:', self._money(contrib.get('total_interest'))],
        ]
        story.append(self._summary_table(rows, '#f0fdf4'))
        story.append(Spacer(1, 0.2*inch))
        return story

    def create_loan_summary(self):
        """Create loan summary section"""
        loans = self.data.get('loans', {})
        story = [Paragraph("LOAN SUMMARY", self.section_style)]

        error = self._error_story(loans)
        if error:
            return story + error
        if not isinstance(loans, dict):
            loans = {}

        rate = float(loans.get('repayment_rate') or 0)
        rows = [
            ['Total Loans:', self._count(loans.get('total_loans'))],
            ['Amount Requested:', self._money(loans.get('total_amount'))],
            ['Amount Disbursed:', self._money(loans.get('total_disbursed'))],
            ['Total Repaid:', self._money(loans.get('total_repaid'))],
            ['Outstanding Balance:', self._money(loans.get('total_balance'))],
            ['Active Loans:', self._count(loans.get('active_loans'))],
            ['Approved Loans:', self._count(loans.get('approved_loans'))],
            ['Completed Loans:', self._count(loans.get('completed_loans'))],
            ['Defaulted Loans:', self._count(loans.get('defaulted_loans'))],
            ['Pending Loans:', self._count(loans.get('pending_loans'))],
            ['Repayment Rate:', f"{rate:.1f}%"],
        ]
        story.append(self._summary_table(rows, '#fef3c7'))
        story.append(Spacer(1, 0.2*inch))
        return story

    def create_transaction_summary(self):
        """Create transaction summary section"""
        transactions = self.data.get('transactions', {})
        story = [Paragraph("TRANSACTION SUMMARY", self.section_style)]

        error = self._error_story(transactions)
        if error:
            return story + error
        if not isinstance(transactions, dict):
            transactions = {}

        rows = [
            ['Total Entries:', self._count(transactions.get('total_entries'))],
            ['Total Debit:', self._money(transactions.get('total_debit'))],
            ['Total Credit:', self._money(transactions.get('total_credit'))],
            ['Net Balance:', self._money(transactions.get('net_balance'))],
        ]
        story.append(self._summary_table(rows, '#dbeafe'))
        story.append(Spacer(1, 0.2*inch))
        return story

    def create_attendance_summary(self):
        """Create attendance summary section"""
        attendance = self.data.get('attendance', {})
        story = [Paragraph("ATTENDANCE SUMMARY", self.section_style)]

        error = self._error_story(attendance)
        if error:
            return story + error
        if not isinstance(attendance, dict):
            attendance = {}

        rate = float(attendance.get('attendance_rate') or 0)
        rows = [
            ['Total Meetings:', self._count(attendance.get('total_meetings'))],
            ['Present:', self._count(attendance.get('present'))],
            ['Absent:', self._count(attendance.get('absent'))],
        ]
        # Only shown when the attendance records actually track "excused"
        if attendance.get('excused') is not None:
            rows.append(['Excused:', self._count(attendance.get('excused'))])
        rows.append(['Attendance Rate:', f"{rate:.1f}%"])

        story.append(self._summary_table(rows, '#f0fdf4'))
        story.append(Spacer(1, 0.2*inch))
        return story

    def create_member_performance(self):
        """Create member performance section"""
        performance = self.data.get('performance', [])
        story = []
        story.append(Paragraph("MEMBER PERFORMANCE", self.section_style))
        
        if not isinstance(performance, list):
            performance = []
        
        if performance and len(performance) > 0:
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
        story = [Paragraph("FINANCIAL SUMMARY", self.section_style)]

        error = self._error_story(financial)
        if error:
            return story + error
        if not isinstance(financial, dict):
            financial = {}

        rows = [
            ['Net Savings (this period):', self._money(financial.get('total_savings'))],
            ['Total Savings Balance (to date):', self._money(financial.get('savings_balance'))],
            ['Social Fund:', self._money(financial.get('total_social_fund'))],
            ['Total Contributions:', self._money(financial.get('total_contributions'))],
            ['Loans Disbursed:', self._money(financial.get('total_loans_disbursed'))],
            ['Loans Repaid:', self._money(financial.get('total_repaid'))],
            ['Outstanding Loan Balance:', self._money(financial.get('outstanding_balance'))],
            ['Total Debit:', self._money(financial.get('total_transactions_debit'))],
            ['Total Credit:', self._money(financial.get('total_transactions_credit'))],
            ['Net Transactions:', self._money(financial.get('net_transactions'))],
            ['Ledger Balance (end of period):', self._money(financial.get('ledger_balance'))],
        ]
        story.append(self._summary_table(rows, '#f3e8ff'))
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