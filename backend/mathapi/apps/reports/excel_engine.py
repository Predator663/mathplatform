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
