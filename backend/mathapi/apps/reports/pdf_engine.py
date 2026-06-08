"""
PDF Export Engine using ReportLab.
Generates professional reports with school header and platform footer.
"""
import io
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ── Brand colours ─────────────────────────────────────────────────────────────
BRAND_BLUE   = colors.HexColor('#2563eb')
BRAND_DARK   = colors.HexColor('#0a0a0f')
BRAND_GRAY   = colors.HexColor('#6b7280')
BRAND_LIGHT  = colors.HexColor('#f3f4f6')
BRAND_GREEN  = colors.HexColor('#10b981')
BRAND_AMBER  = colors.HexColor('#f59e0b')
BRAND_ROSE   = colors.HexColor('#f43f5e')
BRAND_VIOLET = colors.HexColor('#8b5cf6')
WHITE        = colors.white
BLACK        = colors.black

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm


def _grade_color(pct):
    if pct >= 80: return BRAND_GREEN
    if pct >= 60: return BRAND_BLUE
    if pct >= 50: return BRAND_AMBER
    return BRAND_ROSE


def _letter_grade(pct):
    if pct >= 90: return 'A+'
    if pct >= 80: return 'A'
    if pct >= 70: return 'B'
    if pct >= 60: return 'C'
    if pct >= 50: return 'D'
    return 'F'


def _make_styles():
    base = getSampleStyleSheet()
    styles = {}

    styles['title'] = ParagraphStyle('title',
        fontSize=18, fontName='Helvetica-Bold',
        textColor=BRAND_DARK, spaceAfter=2, alignment=TA_LEFT)

    styles['subtitle'] = ParagraphStyle('subtitle',
        fontSize=10, fontName='Helvetica',
        textColor=BRAND_GRAY, spaceAfter=6, alignment=TA_LEFT)

    styles['section'] = ParagraphStyle('section',
        fontSize=11, fontName='Helvetica-Bold',
        textColor=BRAND_DARK, spaceBefore=10, spaceAfter=4)

    styles['body'] = ParagraphStyle('body',
        fontSize=9, fontName='Helvetica',
        textColor=BRAND_DARK, spaceAfter=2)

    styles['footer'] = ParagraphStyle('footer',
        fontSize=8, fontName='Helvetica',
        textColor=BRAND_GRAY, alignment=TA_CENTER)

    styles['meta_label'] = ParagraphStyle('meta_label',
        fontSize=7, fontName='Helvetica-Bold',
        textColor=BRAND_GRAY, spaceAfter=1)

    styles['meta_value'] = ParagraphStyle('meta_value',
        fontSize=9, fontName='Helvetica-Bold',
        textColor=BRAND_DARK)

    return styles


def _header_footer(canvas, doc, meta: dict):
    """Draw page header and footer on every page."""
    canvas.saveState()

    # ── Header bar ──────────────────────────────────────────────────────────
    canvas.setFillColor(BRAND_BLUE)
    canvas.rect(MARGIN, PAGE_H - 2.2*cm, PAGE_W - 2*MARGIN, 1.4*cm, fill=1, stroke=0)

    # Platform name (left)
    canvas.setFillColor(WHITE)
    canvas.setFont('Helvetica-Bold', 14)
    canvas.drawString(MARGIN + 0.3*cm, PAGE_H - 1.45*cm, 'MathPlatform')

    # Σ symbol
    canvas.setFont('Helvetica-Bold', 16)
    canvas.drawString(MARGIN + 0.3*cm - 0.5*cm, PAGE_H - 1.5*cm, '')

    # School name (right of header)
    school = meta.get('school_name', 'School of Excellence')
    canvas.setFont('Helvetica', 9)
    canvas.drawRightString(PAGE_W - MARGIN - 0.3*cm, PAGE_H - 1.3*cm, school)

    canvas.setFont('Helvetica', 8)
    canvas.drawRightString(PAGE_W - MARGIN - 0.3*cm, PAGE_H - 1.75*cm,
                           meta.get('academic_year', ''))

    # ── Sub-header: document title + class info ──────────────────────────────
    canvas.setFillColor(BRAND_DARK)
    canvas.setFont('Helvetica-Bold', 11)
    canvas.drawString(MARGIN, PAGE_H - 3.0*cm, meta.get('doc_title', 'Report'))

    canvas.setFillColor(BRAND_GRAY)
    canvas.setFont('Helvetica', 8)
    sub = meta.get('doc_subtitle', '')
    canvas.drawString(MARGIN, PAGE_H - 3.55*cm, sub)

    # Thin blue rule under sub-header
    canvas.setStrokeColor(BRAND_BLUE)
    canvas.setLineWidth(1)
    canvas.line(MARGIN, PAGE_H - 3.75*cm, PAGE_W - MARGIN, PAGE_H - 3.75*cm)

    # ── Footer ───────────────────────────────────────────────────────────────
    canvas.setStrokeColor(BRAND_LIGHT)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 1.6*cm, PAGE_W - MARGIN, 1.6*cm)

    canvas.setFillColor(BRAND_GRAY)
    canvas.setFont('Helvetica', 7.5)

    # Left: school + platform
    canvas.drawString(MARGIN, 1.2*cm,
        f"{school}  ·  MathPlatform Analytics  ·  {meta.get('academic_year', '')}")

    # Centre: term / exam info
    centre_text = meta.get('footer_centre', '')
    canvas.drawCentredString(PAGE_W / 2, 1.2*cm, centre_text)

    # Right: page number + generated date
    canvas.drawRightString(PAGE_W - MARGIN, 1.2*cm,
        f"Page {doc.page}  ·  Generated {date.today().strftime('%d %b %Y')}")

    canvas.restoreState()


def _meta_grid(meta_items: list, styles) -> Table:
    """Render a row of label/value metadata cells."""
    label_row = [Paragraph(label, styles['meta_label']) for label, _ in meta_items]
    value_row = [Paragraph(str(val), styles['meta_value']) for _, val in meta_items]
    t = Table([label_row, value_row],
              colWidths=[(PAGE_W - 2*MARGIN) / len(meta_items)] * len(meta_items))
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BRAND_LIGHT),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [BRAND_LIGHT, WHITE]),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    return t


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_exam_scores_pdf(exam, scores, sort_by='name', school_name='School of Excellence') -> bytes:
    """
    Generate a PDF of exam scores.
    sort_by: 'name' | 'score_desc' | 'score_asc' | 'grade' | 'student_id'
    """
    scores_list = list(scores)

    sort_map = {
        'name':       lambda s: s.student.full_name.lower(),
        'score_desc': lambda s: -float(s.score),
        'score_asc':  lambda s: float(s.score),
        'grade':      lambda s: s.letter_grade,
        'student_id': lambda s: s.student.student_id,
    }
    scores_list.sort(key=sort_map.get(sort_by, sort_map['name']))

    buf = io.BytesIO()
    styles = _make_styles()

    classroom_names = ', '.join(c.name for c in exam.classrooms.all()) or '—'
    meta = {
        'school_name': school_name,
        'academic_year': exam.academic_year,
        'doc_title': f'{exam.title} — Score Report',
        'doc_subtitle': (
            f'Type: {exam.get_exam_type_display()}  ·  '
            f'Term: {exam.get_term_display()}  ·  '
            f'Date: {exam.exam_date.strftime("%d %b %Y")}  ·  '
            f'Class: {classroom_names}  ·  '
            f'Max Score: {exam.max_score}  ·  '
            f'Pass Mark: {exam.passing_score}'
        ),
        'footer_centre': f'{exam.get_exam_type_display()} · {exam.get_term_display()}',
    }

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=4.2*cm, bottomMargin=2.2*cm,
    )

    story = []

    # ── Summary stats ────────────────────────────────────────────────────────
    present = [s for s in scores_list if not s.is_absent]
    absent  = [s for s in scores_list if s.is_absent]

    if present:
        pcts = [s.percentage for s in present]
        avg = round(sum(pcts) / len(pcts), 1)
        passed = sum(1 for s in present if s.passed)
        pass_rate = round(passed / len(present) * 100, 1)
    else:
        avg = pass_rate = 0

    summary_items = [
        ('STUDENTS', len(scores_list)),
        ('PRESENT', len(present)),
        ('ABSENT', len(absent)),
        ('AVERAGE', f'{avg}%'),
        ('PASS RATE', f'{pass_rate}%'),
        ('HIGHEST', f'{max((s.percentage for s in present), default=0)}%'),
        ('LOWEST', f'{min((s.percentage for s in present), default=0)}%'),
    ]
    story.append(_meta_grid(summary_items, styles))
    story.append(Spacer(1, 0.4*cm))

    # ── Scores table ─────────────────────────────────────────────────────────
    sort_label = {
        'name': 'Sorted by Name',
        'score_desc': 'Sorted by Score (High → Low)',
        'score_asc': 'Sorted by Score (Low → High)',
        'grade': 'Sorted by Grade',
        'student_id': 'Sorted by Student ID',
    }.get(sort_by, '')

    story.append(Paragraph(f'Student Scores  <font color="#6b7280" size="8">({sort_label})</font>', styles['section']))

    col_w = [(PAGE_W - 2*MARGIN) * p for p in [0.05, 0.13, 0.30, 0.10, 0.10, 0.10, 0.10, 0.12]]
    headers = ['#', 'ID', 'Student Name', 'Score', '%', 'Grade', 'Pass?', 'Remarks']
    table_data = [headers]

    for rank, s in enumerate(scores_list, 1):
        if s.is_absent:
            row = [str(rank), s.student.student_id, s.student.full_name,
                   'ABSENT', '—', '—', '—', s.remarks or '']
        else:
            row = [
                str(rank),
                s.student.student_id,
                s.student.full_name,
                f'{float(s.score):.1f}/{float(exam.max_score):.0f}',
                f'{s.percentage}%',
                s.letter_grade,
                '✓' if s.passed else '✗',
                s.remarks or '',
            ]
        table_data.append(row)

    tbl = Table(table_data, colWidths=col_w, repeatRows=1)

    row_styles = [
        ('BACKGROUND', (0,0), (-1,0), BRAND_BLUE),
        ('TEXTCOLOR', (0,0), (-1,0), WHITE),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, BRAND_LIGHT]),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#e5e7eb')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (3,0), (6,-1), 'CENTER'),
    ]

    # Colour pass/fail column
    for i, s in enumerate(scores_list, 1):
        if not s.is_absent:
            color = BRAND_GREEN if s.passed else BRAND_ROSE
            row_styles.append(('TEXTCOLOR', (6, i), (6, i), color))
            row_styles.append(('FONTNAME', (6, i), (6, i), 'Helvetica-Bold'))

    tbl.setStyle(TableStyle(row_styles))
    story.append(tbl)

    doc.build(story, onFirstPage=lambda c, d: _header_footer(c, d, meta),
              onLaterPages=lambda c, d: _header_footer(c, d, meta))
    return buf.getvalue()


def generate_class_report_pdf(classroom, students, scores_map, exams,
                               sort_by='name', school_name='School of Excellence') -> bytes:
    """
    Class performance report: one row per student, one column per exam.
    sort_by: 'name' | 'average_desc' | 'average_asc' | 'student_id'
    """
    buf = io.BytesIO()
    styles = _make_styles()

    exams = list(exams)
    students = list(students)

    # Build student rows with averages
    rows_data = []
    for s in students:
        student_scores = scores_map.get(s.id, {})
        pcts = [v for v in student_scores.values() if v is not None]
        avg = round(sum(pcts) / len(pcts), 1) if pcts else None
        rows_data.append((s, student_scores, avg))

    sort_fns = {
        'name':         lambda x: x[0].full_name.lower(),
        'average_desc': lambda x: -(x[2] or 0),
        'average_asc':  lambda x: (x[2] or 0),
        'student_id':   lambda x: x[0].student_id,
    }
    rows_data.sort(key=sort_fns.get(sort_by, sort_fns['name']))

    meta = {
        'school_name': school_name,
        'academic_year': classroom.academic_year,
        'doc_title': f'{classroom} — Class Performance Report',
        'doc_subtitle': (
            f'Grade: {classroom.grade_level.name}  ·  '
            f'Academic Year: {classroom.academic_year}  ·  '
            f'Students: {len(students)}  ·  '
            f'Exams: {len(exams)}'
        ),
        'footer_centre': f'{classroom.grade_level.name}  ·  {classroom.academic_year}',
    }

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=4.2*cm, bottomMargin=2.2*cm,
    )

    story = []

    # Summary row
    all_avgs = [r[2] for r in rows_data if r[2] is not None]
    class_avg = round(sum(all_avgs) / len(all_avgs), 1) if all_avgs else 0
    story.append(_meta_grid([
        ('CLASS', str(classroom.name)),
        ('GRADE LEVEL', classroom.grade_level.name),
        ('STUDENTS', len(students)),
        ('EXAMS', len(exams)),
        ('CLASS AVERAGE', f'{class_avg}%'),
        ('ACADEMIC YEAR', classroom.academic_year),
    ], styles))
    story.append(Spacer(1, 0.4*cm))

    # ── Per-exam summary ──────────────────────────────────────────────────────
    if exams:
        story.append(Paragraph('Exam Overview', styles['section']))
        exam_sum_data = [['Exam', 'Type', 'Date', 'Max', 'Pass Mark']]
        for e in exams:
            exam_sum_data.append([
                e.title, e.get_exam_type_display(),
                e.exam_date.strftime('%d %b %Y'),
                str(e.max_score), str(e.passing_score),
            ])
        exam_tbl = Table(exam_sum_data,
                         colWidths=[(PAGE_W - 2*MARGIN)*p for p in [0.40, 0.15, 0.18, 0.12, 0.15]],
                         repeatRows=1)
        exam_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), BRAND_DARK),
            ('TEXTCOLOR', (0,0), (-1,0), WHITE),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, BRAND_LIGHT]),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#e5e7eb')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(exam_tbl)
        story.append(Spacer(1, 0.4*cm))

    # ── Student scores matrix ─────────────────────────────────────────────────
    sort_label = {
        'name': 'Sorted by Name',
        'average_desc': 'Sorted by Average (High → Low)',
        'average_asc': 'Sorted by Average (Low → High)',
        'student_id': 'Sorted by Student ID',
    }.get(sort_by, '')

    story.append(Paragraph(f'Student Scores  <font color="#6b7280" size="8">({sort_label})</font>', styles['section']))

    # Truncate exam titles for column headers
    def short(title): return title[:12] + '…' if len(title) > 13 else title

    exam_headers = [short(e.title) for e in exams]
    n = len(exams)
    fixed_cols = 3  # rank, id, name
    total_w = PAGE_W - 2*MARGIN
    fixed_w = total_w * 0.32
    exam_col_w = (total_w - fixed_w - total_w*0.08) / max(n, 1) if n else 1
    avg_w = total_w * 0.08

    col_widths = [total_w*0.04, total_w*0.10, total_w*0.18] + [exam_col_w]*n + [avg_w]
    headers = ['#', 'ID', 'Name'] + exam_headers + ['AVG']
    matrix = [headers]

    for rank, (s, student_scores, avg) in enumerate(rows_data, 1):
        row = [str(rank), s.student_id, s.full_name]
        for e in exams:
            pct = student_scores.get(e.id)
            row.append(f'{pct}%' if pct is not None else '—')
        row.append(f'{avg}%' if avg is not None else '—')
        matrix.append(row)

    mtbl = Table(matrix, colWidths=col_widths, repeatRows=1)
    matrix_styles = [
        ('BACKGROUND', (0,0), (-1,0), BRAND_BLUE),
        ('TEXTCOLOR', (0,0), (-1,0), WHITE),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, BRAND_LIGHT]),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#e5e7eb')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (2,0), (2,-1), 'LEFT'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        # Bold + colour the AVG column
        ('FONTNAME', (-1,1), (-1,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (-1,0), (-1,0), BRAND_DARK),
    ]

    for i, (s, student_scores, avg) in enumerate(rows_data, 1):
        if avg is not None:
            matrix_styles.append(('TEXTCOLOR', (-1,i), (-1,i), _grade_color(avg)))

    mtbl.setStyle(TableStyle(matrix_styles))
    story.append(mtbl)

    doc.build(story, onFirstPage=lambda c, d: _header_footer(c, d, meta),
              onLaterPages=lambda c, d: _header_footer(c, d, meta))
    return buf.getvalue()


def generate_student_report_pdf(student, scores, topic_data,
                                 school_name='School of Excellence') -> bytes:
    """Individual student report card."""
    buf = io.BytesIO()
    styles = _make_styles()
    scores = list(scores)

    pcts = [s.percentage for s in scores if not s.is_absent]
    avg = round(sum(pcts) / len(pcts), 1) if pcts else 0
    passed_count = sum(1 for s in scores if not s.is_absent and s.passed)

    meta = {
        'school_name': school_name,
        'academic_year': scores[0].exam.academic_year if scores else '—',
        'doc_title': f'Student Report — {student.full_name}',
        'doc_subtitle': (
            f'Student ID: {student.student_id}  ·  '
            f'Class: {student.classroom or "—"}  ·  '
            f'Email: {student.email}'
        ),
        'footer_centre': f'Student ID: {student.student_id}',
    }

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=4.2*cm, bottomMargin=2.2*cm,
    )

    story = []

    # ── Summary ───────────────────────────────────────────────────────────────
    story.append(_meta_grid([
        ('STUDENT', student.full_name),
        ('STUDENT ID', student.student_id),
        ('CLASSROOM', str(student.classroom) if student.classroom else '—'),
        ('EXAMS TAKEN', len([s for s in scores if not s.is_absent])),
        ('OVERALL AVG', f'{avg}%'),
        ('EXAMS PASSED', f'{passed_count}/{len([s for s in scores if not s.is_absent])}'),
    ], styles))
    story.append(Spacer(1, 0.4*cm))

    # ── Score history ─────────────────────────────────────────────────────────
    story.append(Paragraph('Examination History', styles['section']))
    col_w = [(PAGE_W - 2*MARGIN)*p for p in [0.04, 0.34, 0.13, 0.13, 0.10, 0.10, 0.08, 0.08]]
    tbl_data = [['#', 'Exam', 'Type', 'Date', 'Score', '%', 'Grade', 'Pass?']]
    for i, s in enumerate(scores, 1):
        if s.is_absent:
            tbl_data.append([str(i), s.exam.title, s.exam.get_exam_type_display(),
                              s.exam.exam_date.strftime('%d %b %Y'), 'ABSENT', '—', '—', '—'])
        else:
            tbl_data.append([
                str(i), s.exam.title, s.exam.get_exam_type_display(),
                s.exam.exam_date.strftime('%d %b %Y'),
                f'{float(s.score):.1f}',
                f'{s.percentage}%',
                s.letter_grade,
                '✓' if s.passed else '✗',
            ])

    tbl = Table(tbl_data, colWidths=col_w, repeatRows=1)
    tstyles = [
        ('BACKGROUND', (0,0), (-1,0), BRAND_DARK),
        ('TEXTCOLOR', (0,0), (-1,0), WHITE),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, BRAND_LIGHT]),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (4,0), (-1,-1), 'CENTER'),
    ]
    for i, s in enumerate(scores, 1):
        if not s.is_absent:
            tbl_styles_color = BRAND_GREEN if s.passed else BRAND_ROSE
            tstyles.append(('TEXTCOLOR', (7, i), (7, i), tbl_styles_color))
            tstyles.append(('FONTNAME', (7, i), (7, i), 'Helvetica-Bold'))
    tbl.setStyle(TableStyle(tstyles))
    story.append(tbl)

    # ── Topic breakdown ───────────────────────────────────────────────────────
    if topic_data:
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph('Topic Mastery', styles['section']))
        topic_rows = [['Topic', 'Average %', 'Grade', 'Attempts', 'Trend']]
        for t in topic_data:
            topic_rows.append([
                t['topic_name'],
                f"{t['average']}%",
                _letter_grade(t['average']),
                str(t['attempts']),
                t['trend'].capitalize(),
            ])
        ttbl = Table(topic_rows,
                     colWidths=[(PAGE_W-2*MARGIN)*p for p in [0.40, 0.15, 0.12, 0.15, 0.18]],
                     repeatRows=1)
        ttbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), BRAND_VIOLET),
            ('TEXTCOLOR', (0,0), (-1,0), WHITE),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, BRAND_LIGHT]),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#e5e7eb')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ]))
        story.append(ttbl)

    doc.build(story, onFirstPage=lambda c, d: _header_footer(c, d, meta),
              onLaterPages=lambda c, d: _header_footer(c, d, meta))
    return buf.getvalue()
