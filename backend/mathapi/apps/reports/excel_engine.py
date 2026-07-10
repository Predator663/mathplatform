"""
Excel Export Engine using openpyxl.
Generates styled workbooks with school header and platform footer.
"""
import io
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import (
    Font, Fill, PatternFill, Alignment, Border, Side, GradientFill
)
from openpyxl.utils import get_column_letter
from openpyxl.styles.numbers import FORMAT_PERCENTAGE_00
from openpyxl.chart import LineChart, BarChart, PieChart, Reference, Series
from openpyxl.chart.marker import DataPoint
from openpyxl.chart.shapes import GraphicalProperties

# ── Brand colours (openpyxl uses ARGB hex) ────────────────────────────────────
BLUE   = '002563eb'
DARK   = 'FF0a0a0f'
GRAY   = 'FF6b7280'
LIGHT  = 'FFF3F4F6'
GREEN  = 'FF10b981'
AMBER  = 'FFf59e0b'
ROSE   = 'FFf43f5e'
VIOLET = 'FF8b5cf6'
WHITE  = 'FFFFFFFF'
HEADER = 'FF1e3a5f'
SUBHDR = 'FF2d4f7c'


def _fill(hex_color): return PatternFill('solid', fgColor=hex_color)
def _font(bold=False, color='FF000000', size=10, italic=False):
    return Font(bold=bold, color=color, size=size, italic=italic, name='Calibri')
def _align(h='left', v='center', wrap=False):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)
def _border(style='thin'):
    s = Side(style=style, color='FFD1D5DB')
    return Border(left=s, right=s, top=s, bottom=s)


def _grade_color_hex(pct):
    # Mirrors pdf_engine._grade_color exactly (and ExamScore.letter_grade
    # bands) so a score is coloured/labelled identically in the PDF and
    # Excel exports and in the app itself.
    if pct >= 75: return GREEN[2:]
    if pct >= 65: return '2563eb'
    if pct >= 45: return AMBER[2:]
    return ROSE[2:]


def _letter_grade_xl(pct):
    if pct >= 75: return 'A'
    if pct >= 65: return 'B'
    if pct >= 45: return 'C'
    if pct >= 30: return 'D'
    return 'F'


def _write_platform_header(ws, school_name, doc_title, doc_subtitle, academic_year, ncols):
    """Write the document header rows at the top of every sheet."""
    # Row 1: Platform name + school
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(1, 1, f'MathPlatform Analytics  ·  {school_name}  ·  {academic_year}')
    c.font = _font(bold=True, color=WHITE, size=12)
    c.fill = _fill(HEADER[2:])  # strip FF prefix
    c.fill = PatternFill('solid', fgColor=HEADER[2:])
    c.alignment = _align('center')
    ws.row_dimensions[1].height = 22

    # Row 2: Document title
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    c2 = ws.cell(2, 1, doc_title)
    c2.font = _font(bold=True, color=WHITE, size=11)
    c2.fill = PatternFill('solid', fgColor=SUBHDR[2:])
    c2.alignment = _align('center')
    ws.row_dimensions[2].height = 18

    # Row 3: Subtitle / meta
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=ncols)
    c3 = ws.cell(3, 1, doc_subtitle)
    c3.font = _font(italic=True, color='FF374151', size=9)
    c3.fill = PatternFill('solid', fgColor='FFE8EFF9')
    c3.alignment = _align('center')
    ws.row_dimensions[3].height = 14

    # Row 4: Generated date
    ws.merge_cells(start_row=4, start_column=1, end_row=4, end_column=ncols)
    c4 = ws.cell(4, 1, f'Generated: {date.today().strftime("%d %B %Y")}')
    c4.font = _font(italic=True, color=GRAY[2:], size=8)
    c4.alignment = _align('right')
    ws.row_dimensions[4].height = 12

    return 5  # next row index


def _freeze_and_autofit(ws, freeze_row, freeze_col, min_widths=None, fixed_cols=None):
    """Freeze panes and auto-size columns to fit their content.

    fixed_cols: optional set of 1-indexed column numbers that should NOT be
    measured against their cell content (e.g. columns holding long, rotated
    header text like exam titles). For those columns, only min_widths is
    used — this stops a single long header from blowing that column out to
    40 chars wide and pushing every other column off-screen/off-page.
    """
    ws.freeze_panes = ws.cell(freeze_row, freeze_col)
    fixed_cols = fixed_cols or set()

    # Cells that anchor a multi-column merge (e.g. the wide "MathPlatform ·
    # School · Year" banner in row 1) hold a full-width string but live in
    # column A. Measuring that string against column A alone used to blow
    # the rank/# column out to ~40 chars wide, overlapping/crowding every
    # column after it. Skip those anchors entirely when sizing.
    merged_anchor_cells = {
        (rng.min_row, rng.min_col)
        for rng in ws.merged_cells.ranges
        if rng.min_col != rng.max_col
    }

    for col in ws.columns:
        col_num = col[0].column
        col_letter = get_column_letter(col_num)
        if col_num in fixed_cols:
            adjusted = (min_widths[col_num - 1]
                        if min_widths and col_num <= len(min_widths) else 10)
            ws.column_dimensions[col_letter].width = adjusted
            continue
        max_len = 0
        for cell in col:
            if (cell.row, cell.column) in merged_anchor_cells:
                continue
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        adjusted = min(max(max_len + 2, 8), 40)
        if min_widths and col_num <= len(min_widths):
            adjusted = max(adjusted, min_widths[col_num - 1])
        ws.column_dimensions[col_letter].width = adjusted


def generate_exam_scores_excel(exam, scores, sort_by='name',
                                school_name='School of Excellence') -> bytes:
    scores_list = list(scores)

    sort_map = {
        'name':       lambda s: s.student.full_name.lower(),
        'score_desc': lambda s: -float(s.score),
        'score_asc':  lambda s: float(s.score),
        'grade':      lambda s: s.letter_grade,
        'student_id': lambda s: s.student.student_id,
    }
    scores_list.sort(key=sort_map.get(sort_by, sort_map['name']))

    wb = Workbook()
    ws = wb.active
    ws.title = 'Scores'
    ws.sheet_view.showGridLines = False

    classroom_names = ', '.join(c.name for c in exam.classrooms.all()) or '—'
    present = [s for s in scores_list if not s.is_absent]
    absent_count = len(scores_list) - len(present)
    pcts = [s.percentage for s in present]
    avg = round(sum(pcts)/len(pcts), 1) if pcts else 0
    pass_rate = round(sum(1 for s in present if s.passed)/len(present)*100, 1) if present else 0

    ncols = 8
    next_row = _write_platform_header(
        ws, school_name,
        f'{exam.title} — Score Report',
        f'Type: {exam.get_exam_type_display()}  |  Term: {exam.get_term_display()}  |  '
        f'Date: {exam.exam_date.strftime("%d %b %Y")}  |  Class: {classroom_names}  |  '
        f'Max: {exam.max_score}  |  Pass: {exam.passing_score}',
        exam.academic_year,
        ncols
    )

    # Summary stats row
    next_row += 1
    stats = [('Students', len(scores_list)), ('Present', len(present)), ('Absent', absent_count),
             ('Average', f'{avg}%' if pcts else '—'), ('Pass Rate', f'{pass_rate}%' if present else '—'),
             ('Highest', f'{max(pcts)}%' if pcts else '—'), ('Lowest', f'{min(pcts)}%' if pcts else '—')]
    for j, (label, val) in enumerate(stats, 1):
        lc = ws.cell(next_row, j, label)
        lc.font = _font(bold=True, color='FF6B7280', size=7)
        lc.alignment = _align('center')
        vc = ws.cell(next_row+1, j, val)
        vc.font = _font(bold=True, size=10)
        vc.fill = PatternFill('solid', fgColor='FFE8EFF9')
        vc.alignment = _align('center')
        vc.border = _border()
    next_row += 3

    # Column headers
    col_headers = ['#', 'Student ID', 'Student Name', 'Score', 'Max Score', '% Score', 'Grade', 'Pass?']
    for j, h in enumerate(col_headers, 1):
        c = ws.cell(next_row, j, h)
        c.font = _font(bold=True, color=WHITE, size=9)
        c.fill = PatternFill('solid', fgColor=HEADER[2:])
        c.alignment = _align('center')
        c.border = _border()
    ws.row_dimensions[next_row].height = 18
    next_row += 1
    data_start = next_row

    for rank, s in enumerate(scores_list, 1):
        is_even = rank % 2 == 0
        row_fill = PatternFill('solid', fgColor='FFF8FAFC') if is_even else PatternFill('solid', fgColor=WHITE)

        if s.is_absent:
            row_data = [rank, s.student.student_id, s.student.full_name, 'ABSENT', exam.max_score, '—', '—', '—']
        else:
            row_data = [rank, s.student.student_id, s.student.full_name,
                        float(s.score), float(exam.max_score), s.percentage/100,
                        s.letter_grade, 'Pass' if s.passed else 'Fail']

        for j, val in enumerate(row_data, 1):
            c = ws.cell(next_row, j, val)
            c.fill = row_fill
            c.border = _border()
            c.alignment = _align('center' if j != 3 else 'left')
            c.font = _font(size=9)

        # Percentage as percentage format
        if not s.is_absent:
            ws.cell(next_row, 6).number_format = '0.0%'
            # Colour pass/fail
            pf_cell = ws.cell(next_row, 8)
            pf_cell.font = _font(bold=True, size=9,
                                  color=GREEN[2:] if s.passed else ROSE[2:])
            # Colour grade
            ws.cell(next_row, 7).font = _font(bold=True, size=9,
                color=GREEN[2:] if s.percentage>=75 else AMBER[2:] if s.percentage>=45 else ROSE[2:])

        next_row += 1

    # Totals row
    ws.cell(next_row, 3, 'CLASS AVERAGE').font = _font(bold=True, size=9)
    ws.cell(next_row, 6, avg/100).number_format = '0.0%'
    ws.cell(next_row, 6).font = _font(bold=True, size=9)
    for j in range(1, ncols+1):
        ws.cell(next_row, j).fill = PatternFill('solid', fgColor='FFE8EFF9')
        ws.cell(next_row, j).border = _border()

    _freeze_and_autofit(ws, data_start, 3)

    # ── Summary sheet ─────────────────────────────────────────────────────────
    ws2 = wb.create_sheet('Summary')
    ws2.sheet_view.showGridLines = False
    _write_platform_header(ws2, school_name, f'{exam.title} — Summary',
                            f'Generated: {date.today().strftime("%d %b %Y")}', exam.academic_year, 4)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generate_class_report_excel(classroom, students, scores_map, exams,
                                  sort_by='name', school_name='School of Excellence') -> bytes:
    students = list(students)
    exams = list(exams)

    rows_data = []
    for s in students:
        s_scores = scores_map.get(s.id, {})
        pcts = [v for v in s_scores.values() if v is not None]
        avg = round(sum(pcts)/len(pcts), 1) if pcts else None
        rows_data.append((s, s_scores, avg))

    sort_fns = {
        'name':         lambda x: x[0].full_name.lower(),
        'average_desc': lambda x: -(x[2] or 0),
        'average_asc':  lambda x: (x[2] or 0),
        'student_id':   lambda x: x[0].student_id,
    }
    rows_data.sort(key=sort_fns.get(sort_by, sort_fns['name']))

    wb = Workbook()
    ws = wb.active
    ws.title = 'Class Report'
    ws.sheet_view.showGridLines = False

    ncols = 3 + len(exams) + 1  # rank, id, name + exams + avg
    _write_platform_header(
        ws, school_name,
        f'{classroom} — Class Performance Report',
        f'Grade: {classroom.grade_level.name}  |  Year: {classroom.academic_year}  |  '
        f'Students: {len(students)}  |  Exams: {len(exams)}',
        classroom.academic_year,
        ncols
    )

    next_row = 6
    col_headers = ['#', 'Student ID', 'Name'] + [e.title for e in exams] + ['AVERAGE']
    # Exam-title columns are rotated 90° so a long exam name doesn't force
    # the column itself to widen (which used to push later columns off the
    # printable page and made scores overlap the header text). The rank/ID/
    # name/average columns stay horizontal since they're short labels.
    exam_col_nums = set(range(4, 4 + len(exams)))
    for j, h in enumerate(col_headers, 1):
        c = ws.cell(next_row, j, h)
        c.font = _font(bold=True, color=WHITE, size=8)
        bg = HEADER[2:] if j <= 3 or j == ncols else SUBHDR[2:]
        c.fill = PatternFill('solid', fgColor=bg)
        if j in exam_col_nums:
            c.alignment = Alignment(horizontal='center', vertical='bottom',
                                     wrap_text=True, text_rotation=90)
        else:
            c.alignment = _align('center', wrap=True)
        c.border = _border()
    # Tall enough to fit rotated exam titles without clipping or overlapping
    # the data rows beneath them.
    ws.row_dimensions[next_row].height = 110
    next_row += 1

    all_avgs = []
    for rank, (s, s_scores, avg) in enumerate(rows_data, 1):
        is_even = rank % 2 == 0
        row_fill = PatternFill('solid', fgColor='FFF8FAFC') if is_even else PatternFill('solid', fgColor=WHITE)

        ws.cell(next_row, 1, rank).fill = row_fill
        ws.cell(next_row, 1).border = _border()
        ws.cell(next_row, 1).alignment = _align('center')

        ws.cell(next_row, 2, s.student_id).fill = row_fill
        ws.cell(next_row, 2).border = _border()
        ws.cell(next_row, 2).alignment = _align('center')
        ws.cell(next_row, 2).font = _font(size=8)

        ws.cell(next_row, 3, s.full_name).fill = row_fill
        ws.cell(next_row, 3).border = _border()
        ws.cell(next_row, 3).font = _font(size=8)

        for ei, e in enumerate(exams, 4):
            pct = s_scores.get(e.id)
            c = ws.cell(next_row, ei, f'{pct}%' if pct is not None else '—')
            c.fill = row_fill
            c.border = _border()
            c.alignment = _align('center')
            c.font = _font(size=8,
                color=GREEN[2:] if pct is not None and pct>=75 else AMBER[2:] if pct is not None and pct>=45 else ROSE[2:] if pct is not None else GRAY[2:])

        avg_c = ws.cell(next_row, ncols, f'{avg}%' if avg is not None else '—')
        avg_c.fill = PatternFill('solid', fgColor='FFE8EFF9')
        avg_c.font = _font(bold=True, size=8,
            color=GREEN[2:] if avg is not None and avg>=75 else AMBER[2:] if avg is not None and avg>=45 else ROSE[2:] if avg is not None else GRAY[2:])
        avg_c.border = _border()
        avg_c.alignment = _align('center')
        if avg is not None: all_avgs.append(avg)
        next_row += 1

    # Class average footer row
    class_avg = round(sum(all_avgs)/len(all_avgs), 1) if all_avgs else None
    ws.cell(next_row, 3, 'CLASS AVERAGE').font = _font(bold=True, size=9)
    avg_footer_c = ws.cell(next_row, ncols, f'{class_avg}%' if class_avg is not None else '—')
    avg_footer_c.font = _font(bold=True, size=9,
        color=(GREEN[2:] if class_avg is not None and class_avg>=75
               else AMBER[2:] if class_avg is not None and class_avg>=45
               else ROSE[2:] if class_avg is not None else GRAY[2:]))
    for j in range(1, ncols+1):
        ws.cell(next_row, j).fill = PatternFill('solid', fgColor='FFD1FAE5')
        ws.cell(next_row, j).border = _border()

    # Exam columns get a fixed narrow width (they hold "87%" style values,
    # not the rotated header text) instead of being auto-sized off the long
    # exam title — that autofit was the source of the column blowout.
    min_widths = [4, 12, 22] + [9] * len(exams) + [10]
    _freeze_and_autofit(ws, 7, 4, min_widths=min_widths, fixed_cols=exam_col_nums)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _std_dev_xl(values):
    if len(values) < 2:
        return 0
    m = sum(values) / len(values)
    return (sum((v - m) ** 2 for v in values) / len(values)) ** 0.5


def generate_student_report_excel(student, scores, topic_data,
                                   school_name='School of Excellence',
                                   trend=None, comparison=None) -> bytes:
    """
    Individual student report, Excel version — mirrors generate_student_report_pdf.

    Sheets: Summary (KPIs + narrative + 4 native charts, each with a proper
    legend), Exam History (with classroom-average comparison columns),
    Topic Mastery, Term Breakdown. Chart source data lives on a hidden
    '_ChartData' sheet so the Summary sheet itself stays readable.
    """
    scores = list(scores)
    trend = trend or {}
    comparison = comparison or {}
    class_by_exam = comparison.get('by_exam') or {}
    rank = comparison.get('rank')
    class_size = comparison.get('class_size') or 0
    percentile = comparison.get('percentile')

    present = [s for s in scores if not s.is_absent]
    pcts = [s.percentage for s in present]
    avg = round(sum(pcts) / len(pcts), 1) if pcts else None
    passed_count = sum(1 for s in present if s.passed)
    highest = max(pcts) if pcts else None
    lowest = min(pcts) if pcts else None
    consistency = round(_std_dev_xl(pcts), 1) if len(pcts) > 1 else 0
    trend_label = (trend.get('trend') or 'no_data').replace('_', ' ').capitalize()

    timeline = trend.get('timeline') or [
        {'exam_id': s.exam_id, 'exam_title': s.exam.title,
         'exam_date': s.exam.exam_date.strftime('%Y-%m-%d'), 'percentage': s.percentage}
        for s in present
    ]
    moving_average = trend.get('moving_average') or []

    wb = Workbook()

    # ── Hidden chart-data sheet ──────────────────────────────────────────────
    dws = wb.create_sheet('_ChartData')
    dws.sheet_state = 'hidden'

    # Trend block: columns A-D
    dws.cell(1, 1, 'Exam'); dws.cell(1, 2, 'Score %'); dws.cell(1, 3, 'Moving Avg'); dws.cell(1, 4, 'Class Avg')
    for i, t in enumerate(timeline, 2):
        dws.cell(i, 1, t['exam_date'][5:])
        dws.cell(i, 2, t['percentage'])
        ma = moving_average[i-2] if i-2 < len(moving_average) else None
        dws.cell(i, 3, ma if ma is not None else None)
        dws.cell(i, 4, class_by_exam.get(t.get('exam_id')))
    trend_rows = len(timeline)

    # Topic block: columns F-G
    dws.cell(1, 6, 'Topic'); dws.cell(1, 7, 'Average')
    for i, t in enumerate(topic_data, 2):
        dws.cell(i, 6, t['topic_name'])
        dws.cell(i, 7, t['average'])
    topic_rows = len(topic_data)

    # Grade distribution block: columns I-J
    grade_counts = {}
    for s in present:
        g = s.letter_grade
        grade_counts[g] = grade_counts.get(g, 0) + 1
    order = ['A', 'B', 'C', 'D', 'F']
    grade_labels = [g for g in order if g in grade_counts]
    dws.cell(1, 9, 'Grade'); dws.cell(1, 10, 'Count')
    for i, g in enumerate(grade_labels, 2):
        dws.cell(i, 9, g)
        dws.cell(i, 10, grade_counts[g])
    grade_rows = len(grade_labels)

    # Comparison block: columns L-N (only exams with a classroom average)
    cmp_timeline = [t for t in timeline if t.get('exam_id') in class_by_exam]
    dws.cell(1, 12, 'Exam'); dws.cell(1, 13, 'Student %'); dws.cell(1, 14, 'Class Avg %')
    for i, t in enumerate(cmp_timeline, 2):
        dws.cell(i, 12, t['exam_title'][:20])
        dws.cell(i, 13, t['percentage'])
        dws.cell(i, 14, class_by_exam[t['exam_id']])
    cmp_rows = len(cmp_timeline)

    # ── Summary sheet ─────────────────────────────────────────────────────────
    ws = wb.active
    ws.title = 'Summary'
    ws.sheet_view.showGridLines = False

    ncols = 6
    next_row = _write_platform_header(
        ws, school_name, f'Individual Student Report — {student.full_name}',
        f'Student ID: {student.student_id}  |  Class: {student.classroom or "—"}  |  '
        f'Email: {student.email}',
        scores[0].exam.academic_year if scores else '—', ncols,
    )
    next_row += 1

    kpis = [
        ('Exams Taken', len(present)), ('Overall Avg', f'{avg}%' if avg is not None else '—'),
        ('Pass Rate', f'{round(passed_count/len(present)*100, 1)}%' if present else '—'),
        ('Highest', f'{highest}%' if highest is not None else '—'),
        ('Lowest', f'{lowest}%' if lowest is not None else '—'),
        ('Consistency (σ)', f'{consistency} pts'),
    ]
    for j, (label, val) in enumerate(kpis, 1):
        lc = ws.cell(next_row, j, label)
        lc.font = _font(bold=True, color='FF6B7280', size=7)
        lc.alignment = _align('center')
        vc = ws.cell(next_row+1, j, val)
        vc.font = _font(bold=True, size=11)
        vc.fill = PatternFill('solid', fgColor='FFE8EFF9')
        vc.alignment = _align('center')
        vc.border = _border()
    next_row += 2

    kpis2 = [
        ('Trend', trend_label), ('Predicted Grade', _letter_grade_xl(avg) if avg is not None else '—'),
        ('Class Rank', f'{rank} of {class_size}' if rank else '—'),
        ('Percentile', f'Top {round(100 - percentile, 1)}%' if percentile is not None else '—'),
        ('Classmates Compared', str(class_size) if class_size else '—'), ('', ''),
    ]
    for j, (label, val) in enumerate(kpis2, 1):
        if not label:
            continue
        lc = ws.cell(next_row, j, label)
        lc.font = _font(bold=True, color='FF6B7280', size=7)
        lc.alignment = _align('center')
        vc = ws.cell(next_row+1, j, val)
        vc.font = _font(bold=True, size=11)
        vc.fill = PatternFill('solid', fgColor='FFF3F0FF')
        vc.alignment = _align('center')
        vc.border = _border()
    next_row += 3

    # Narrative
    if topic_data:
        sorted_topics = sorted(topic_data, key=lambda t: t['average'], reverse=True)
        strong = [t['topic_name'] for t in sorted_topics if t['average'] >= 70][:3]
        weak = [t['topic_name'] for t in sorted_topics if t['average'] < 50][:3]
        lines = []
        if strong: lines.append(f"Strengths: {', '.join(strong)}.")
        if weak: lines.append(f"Watch areas: {', '.join(weak)}.")
        if not strong and not weak: lines.append('Performance is fairly even across topics.')
        ws.merge_cells(start_row=next_row, start_column=1, end_row=next_row, end_column=ncols)
        c = ws.cell(next_row, 1, '  ·  '.join(lines))
        c.font = _font(italic=True, size=9, color='FF374151')
        c.alignment = _align('left', wrap=True)
        ws.row_dimensions[next_row].height = 16
        next_row += 2

    charts_top = next_row

    # Trend chart (Score % / Moving Avg / Class Avg) — legend on by default
    if trend_rows >= 2:
        lc = LineChart()
        lc.title = 'Score Trend Over Time'
        lc.style = 2
        lc.y_axis.title = '%'
        lc.y_axis.scaling.min = 0
        lc.y_axis.scaling.max = 100
        lc.x_axis.title = 'Exam'
        cats = Reference(dws, min_col=1, min_row=2, max_row=1+trend_rows)
        for col, name in [(2, 'Score %'), (3, 'Moving avg (3)'), (4, 'Classroom avg')]:
            has_any = any(
                dws.cell(r, col).value is not None for r in range(2, 2+trend_rows)
            )
            if not has_any:
                continue
            data = Reference(dws, min_col=col, min_row=1, max_row=1+trend_rows)
            lc.add_data(data, titles_from_data=True)
        lc.set_categories(cats)
        lc.width, lc.height = 17, 9
        ws.add_chart(lc, f'A{charts_top}')

    # Topic mastery bar chart — coloured per bar by performance band
    if topic_rows:
        bc = BarChart()
        bc.type = 'col'
        bc.title = 'Topic Mastery'
        bc.y_axis.title = '%'
        bc.y_axis.scaling.min = 0
        bc.y_axis.scaling.max = 100
        data = Reference(dws, min_col=7, min_row=1, max_row=1+topic_rows)
        cats = Reference(dws, min_col=6, min_row=2, max_row=1+topic_rows)
        bc.add_data(data, titles_from_data=True)
        bc.set_categories(cats)
        series = bc.series[0]
        series.data_points = [
            DataPoint(idx=i, graphicalProperties=GraphicalProperties(
                solidFill=_grade_color_hex(t['average'])))
            for i, t in enumerate(topic_data)
        ]
        bc.legend = None  # per-bar colours aren't a single legend-able series; key given below instead
        bc.width, bc.height = 12, 9
        ws.add_chart(bc, f'H{charts_top}')
        # Manual colour key, since a single-series chart can't show a
        # per-point legend natively in Excel.
        key_row = charts_top + 19
        ws.cell(key_row, 8, 'Colour key:').font = _font(bold=True, size=8)
        for i, (label, hexcolor) in enumerate([
            ('Strong (75%+)', GREEN[2:]), ('Good (65-74%)', '2563eb'),
            ('Fair (45-64%)', AMBER[2:]), ('Needs support (<45%)', ROSE[2:]),
        ]):
            cc = ws.cell(key_row + 1 + i, 8, '  ' + label)
            cc.font = _font(size=8)
            cc.fill = PatternFill('solid', fgColor=hexcolor)

    charts_top2 = charts_top + 20

    # Grade distribution pie chart — legend on by default
    if grade_rows:
        pc = PieChart()
        pc.title = 'Grade Distribution'
        data = Reference(dws, min_col=10, min_row=1, max_row=1+grade_rows)
        cats = Reference(dws, min_col=9, min_row=2, max_row=1+grade_rows)
        pc.add_data(data, titles_from_data=True)
        pc.set_categories(cats)
        grade_hex = {'A': GREEN[2:], 'B': '2563eb', 'C': AMBER[2:], 'D': 'fb923c', 'F': ROSE[2:]}
        pc.series[0].data_points = [
            DataPoint(idx=i, graphicalProperties=GraphicalProperties(
                solidFill=grade_hex.get(g, GRAY[2:])))
            for i, g in enumerate(grade_labels)
        ]
        pc.width, pc.height = 12, 9
        ws.add_chart(pc, f'A{charts_top2}')

    # Student vs classroom average, per exam — legend on by default
    if cmp_rows:
        cbc = BarChart()
        cbc.type = 'col'
        cbc.grouping = 'clustered'
        cbc.title = 'Student vs. Classroom Average'
        cbc.y_axis.title = '%'
        cbc.y_axis.scaling.min = 0
        cbc.y_axis.scaling.max = 100
        cats = Reference(dws, min_col=12, min_row=2, max_row=1+cmp_rows)
        data = Reference(dws, min_col=13, max_col=14, min_row=1, max_row=1+cmp_rows)
        cbc.add_data(data, titles_from_data=True)
        cbc.set_categories(cats)
        cbc.series[0].graphicalProperties.solidFill = '2563eb'
        cbc.series[1].graphicalProperties.solidFill = GRAY[2:]
        cbc.width, cbc.height = 12, 9
        ws.add_chart(cbc, f'H{charts_top2}')

    ws.column_dimensions['A'].width = 14
    for col in 'BCDEF':
        ws.column_dimensions[col].width = 12

    # ── Exam History sheet ───────────────────────────────────────────────────
    hws = wb.create_sheet('Exam History')
    hws.sheet_view.showGridLines = False
    has_cmp = bool(class_by_exam)
    hcols = 11 if has_cmp else 8
    _write_platform_header(hws, school_name, f'{student.full_name} — Exam History',
                            'Class Avg / vs Class show the classroom average on that same '
                            'exam and the student\'s difference from it.' if has_cmp else
                            'Full record of every exam taken.',
                            scores[0].exam.academic_year if scores else '—', hcols)
    hr = 6
    headers = ['#', 'Exam', 'Type', 'Date', 'Score', '%'] + \
              (['Class Avg', 'vs Class'] if has_cmp else []) + ['Grade', 'Pass?']
    for j, h in enumerate(headers, 1):
        c = hws.cell(hr, j, h)
        c.font = _font(bold=True, color=WHITE, size=9)
        c.fill = PatternFill('solid', fgColor=HEADER[2:])
        c.alignment = _align('center')
        c.border = _border()
    hws.row_dimensions[hr].height = 18
    hr += 1
    for i, s in enumerate(scores, 1):
        row_fill = PatternFill('solid', fgColor='FFF8FAFC') if i % 2 == 0 else PatternFill('solid', fgColor=WHITE)
        vals = [i, s.exam.title, s.exam.get_exam_type_display(), s.exam.exam_date.strftime('%d %b %Y')]
        if s.is_absent:
            vals += ['ABSENT', '—'] + (['—', '—'] if has_cmp else []) + ['—', '—']
        else:
            vals += [float(s.score), s.percentage/100]
            if has_cmp:
                cavg = class_by_exam.get(s.exam_id)
                diff = round(s.percentage - cavg, 1) if cavg is not None else None
                vals += [cavg/100 if cavg is not None else '—', f'{"+" if diff and diff>0 else ""}{diff}%' if diff is not None else '—']
            vals += [s.letter_grade, 'Pass' if s.passed else 'Fail']
        for j, v in enumerate(vals, 1):
            c = hws.cell(hr, j, v)
            c.fill = row_fill
            c.border = _border()
            c.alignment = _align('center' if j != 2 else 'left')
            c.font = _font(size=9)
            if j == 6 and not s.is_absent:
                c.number_format = '0.0%'
            if has_cmp and j == 7 and not s.is_absent:
                c.number_format = '0.0%'
        if not s.is_absent:
            pass_col = 9 if has_cmp else 8
            pc = hws.cell(hr, pass_col)
            pc.font = _font(bold=True, size=9, color=GREEN[2:] if s.passed else ROSE[2:])
            if has_cmp:
                cavg = class_by_exam.get(s.exam_id)
                if cavg is not None:
                    diff_c = hws.cell(hr, 7)
                    diff_c.font = _font(bold=True, size=9,
                                         color=GREEN[2:] if s.percentage >= cavg else ROSE[2:])
        hr += 1
    _freeze_and_autofit(hws, 7, 2, min_widths=[4, 24, 12, 11, 8, 8] + ([9, 9] if has_cmp else []) + [7, 7])

    # ── Topic Mastery sheet ──────────────────────────────────────────────────
    if topic_data:
        tws = wb.create_sheet('Topic Mastery')
        tws.sheet_view.showGridLines = False
        _write_platform_header(tws, school_name, f'{student.full_name} — Topic Mastery',
                                'Average performance broken down by topic.',
                                scores[0].exam.academic_year if scores else '—', 7)
        tr = 6
        for j, h in enumerate(['Topic', 'Average %', 'Grade', 'Attempts', 'Highest', 'Lowest', 'Trend'], 1):
            c = tws.cell(tr, j, h)
            c.font = _font(bold=True, color=WHITE, size=9)
            c.fill = PatternFill('solid', fgColor=VIOLET[2:])
            c.alignment = _align('center')
            c.border = _border()
        tr += 1
        for t in topic_data:
            row_fill = PatternFill('solid', fgColor='FFF8FAFC') if tr % 2 == 0 else PatternFill('solid', fgColor=WHITE)
            vals = [t['topic_name'], t['average']/100, _letter_grade_xl(t['average']),
                    t['attempts'], t.get('highest', 0)/100, t.get('lowest', 0)/100, t['trend'].capitalize()]
            for j, v in enumerate(vals, 1):
                c = tws.cell(tr, j, v)
                c.fill = row_fill
                c.border = _border()
                c.alignment = _align('center' if j != 1 else 'left')
                c.font = _font(size=9,
                    color=_grade_color_hex(t['average']) if j == 2 else '000000', bold=(j == 2))
                if j in (2, 5, 6):
                    c.number_format = '0.0%'
            tr += 1
        _freeze_and_autofit(tws, 7, 2, min_widths=[22, 10, 8, 9, 9, 9, 10])

    # ── Term Breakdown sheet ─────────────────────────────────────────────────
    term_groups = {}
    term_labels = {}
    for s in present:
        key = (s.exam.academic_year, s.exam.term)
        term_groups.setdefault(key, []).append(s.percentage)
        term_labels[key] = s.exam.get_term_display()
    if term_groups:
        rws = wb.create_sheet('Term Breakdown')
        rws.sheet_view.showGridLines = False
        _write_platform_header(rws, school_name, f'{student.full_name} — Term-by-Term Performance',
                                'Average, highest and lowest score per academic term.',
                                scores[0].exam.academic_year if scores else '—', 6)
        rr = 6
        for j, h in enumerate(['Academic Year', 'Term', 'Exams', 'Average', 'Highest', 'Lowest'], 1):
            c = rws.cell(rr, j, h)
            c.font = _font(bold=True, color=WHITE, size=9)
            c.fill = PatternFill('solid', fgColor=HEADER[2:])
            c.alignment = _align('center')
            c.border = _border()
        rr += 1
        for (year, term), vals in sorted(term_groups.items()):
            row_fill = PatternFill('solid', fgColor='FFF8FAFC') if rr % 2 == 0 else PatternFill('solid', fgColor=WHITE)
            row = [year, term_labels[(year, term)], len(vals),
                   round(sum(vals)/len(vals), 1)/100, max(vals)/100, min(vals)/100]
            for j, v in enumerate(row, 1):
                c = rws.cell(rr, j, v)
                c.fill = row_fill
                c.border = _border()
                c.alignment = _align('center')
                c.font = _font(size=9)
                if j in (4, 5, 6):
                    c.number_format = '0.0%'
            rr += 1
        _freeze_and_autofit(rws, 7, 3, min_widths=[14, 12, 8, 10, 10, 10])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
