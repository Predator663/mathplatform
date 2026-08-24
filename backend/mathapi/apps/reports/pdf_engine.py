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
    Spacer, HRFlowable, KeepTogether, PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.widgets.markers import makeMarker

from .badge_art import draw_badge_drawing, icon_color

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
    # Aligned with ExamScore.letter_grade bands (exams/models.py) so PDF
    # coloring never contradicts the grade actually stored/shown elsewhere.
    if pct >= 75: return BRAND_GREEN
    if pct >= 65: return BRAND_BLUE
    if pct >= 45: return BRAND_AMBER
    return BRAND_ROSE


def _letter_grade(pct):
    # Must mirror ExamScore.letter_grade (exams/models.py) exactly. Previously
    # this used an unrelated 90/80/70/60/50 A+/A/B/C/D/F scale, which meant
    # the same score could show as e.g. "A" in the exam history table (using
    # the real model property) and "B" in the pie chart / predicted grade on
    # the same PDF (using this function). Keep these two in sync if the
    # official grade bands ever change.
    if pct >= 75: return 'A'
    if pct >= 65: return 'B'
    if pct >= 45: return 'C'
    if pct >= 30: return 'D'
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

    styles['caption'] = ParagraphStyle('caption',
        fontSize=7.5, fontName='Helvetica-Oblique',
        textColor=BRAND_GRAY, spaceBefore=4, leading=10)

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
    canvas.drawString(MARGIN + 0.3*cm, PAGE_H - 1.45*cm,
                       meta.get('platform_name') or meta.get('school_name', 'MathPlatform'))

    # School name (right of header) — sourced from the Settings page
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
        f"{school}  ·  Generated by {meta.get('platform_name') or 'MathPlatform'}")

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


# ── Chart builders (native ReportLab vector graphics, no extra deps) ──────────

CHART_W = (PAGE_W - 2*MARGIN)
CHART_H = 6.0 * cm


def _trend_chart(timeline, moving_average, class_avg_series=None, width=CHART_W, height=CHART_H) -> Drawing:
    """Line chart: % score per exam over time, a 3-exam moving average, and
    (when available) the classroom average on those same exams — so a
    student's trajectory can be read against their peers, not in isolation."""
    d = Drawing(width, height)
    if len(timeline) < 2:
        d.add(String(width/2, height/2, 'Not enough exams yet for a trend chart',
                      fontSize=9, fillColor=BRAND_GRAY, textAnchor='middle'))
        return d

    pcts = [t['percentage'] for t in timeline]
    n = len(pcts)
    score_series = list(zip(range(n), pcts))
    avg_series = [(i, v) for i, v in enumerate(moving_average) if v is not None] if moving_average else []
    class_series = (
        [(i, v) for i, v in enumerate(class_avg_series) if v is not None]
        if class_avg_series else []
    )

    plot = LinePlot()
    plot.x = 1.6*cm
    plot.y = 1.3*cm
    plot.width = width - 2.6*cm
    plot.height = height - 2.0*cm
    plot.data = [score_series] + ([avg_series] if avg_series else []) + ([class_series] if class_series else [])

    plot.lines[0].strokeColor = BRAND_BLUE
    plot.lines[0].strokeWidth = 1.6
    plot.lines[0].symbol = makeMarker('FilledCircle')
    plot.lines[0].symbol.fillColor = BRAND_BLUE
    plot.lines[0].symbol.strokeColor = BRAND_BLUE
    plot.lines[0].symbol.size = 3
    next_idx = 1
    if avg_series:
        plot.lines[next_idx].strokeColor = BRAND_VIOLET
        plot.lines[next_idx].strokeWidth = 1.2
        plot.lines[next_idx].strokeDashArray = [3, 2]
        next_idx += 1
    if class_series:
        plot.lines[next_idx].strokeColor = BRAND_GRAY
        plot.lines[next_idx].strokeWidth = 1.2
        plot.lines[next_idx].strokeDashArray = [1, 2]

    plot.xValueAxis.valueMin = 0
    plot.xValueAxis.valueMax = n - 1
    plot.xValueAxis.valueSteps = list(range(n))
    plot.xValueAxis.labelTextFormat = lambda v: (
        timeline[int(v)]['exam_date'][5:] if 0 <= int(v) < n else ''
    )
    plot.xValueAxis.labels.fontSize = 6.5
    plot.xValueAxis.labels.angle = 30
    plot.xValueAxis.labels.dy = -8

    plot.yValueAxis.valueMin = 0
    plot.yValueAxis.valueMax = 100
    plot.yValueAxis.valueSteps = [0, 25, 50, 75, 100]
    plot.yValueAxis.labelTextFormat = '%d%%'
    plot.yValueAxis.labels.fontSize = 7

    d.add(plot)

    legend = Legend()
    legend.x = plot.x + 4
    legend.y = height - 0.15*cm
    legend.alignment = 'right'
    legend.fontSize = 7
    legend.dx = 7
    legend.dy = 7
    legend.deltax = 60
    legend.columnMaximum = 1
    legend.colorNamePairs = (
        [(BRAND_BLUE, 'Score %')]
        + ([(BRAND_VIOLET, 'Moving avg (3)')] if avg_series else [])
        + ([(BRAND_GRAY, 'Classroom avg')] if class_series else [])
    )
    d.add(legend)

    # 50% pass-mark reference line
    pass_y = plot.y + (50/100) * plot.height
    d.add(String(plot.x + plot.width - 0.1*cm, pass_y + 2, '50% pass mark',
                  fontSize=6, fillColor=BRAND_GRAY, textAnchor='end'))
    from reportlab.graphics.shapes import Line
    d.add(Line(plot.x, pass_y, plot.x + plot.width, pass_y,
               strokeColor=BRAND_AMBER, strokeWidth=0.5, strokeDashArray=[2, 2]))

    return d


def _topic_bar_chart(topics, width=CHART_W, height=CHART_H) -> Drawing:
    """Vertical bar chart of average % per topic, colour-banded by
    performance with an explicit legend/key (previously the bars were
    colour-coded with no key explaining what the colours meant)."""
    d = Drawing(width, height)
    if not topics:
        d.add(String(width/2, height/2, 'No topic-level data recorded yet',
                      fontSize=9, fillColor=BRAND_GRAY, textAnchor='middle'))
        return d

    chart = VerticalBarChart()
    chart.x = 1.6*cm
    chart.y = 1.6*cm
    chart.width = width - 2.4*cm
    chart.height = height - 2.9*cm
    chart.data = [[t['average'] for t in topics]]
    chart.categoryAxis.categoryNames = [
        (t['topic_name'][:14] + '…') if len(t['topic_name']) > 15 else t['topic_name']
        for t in topics
    ]
    chart.categoryAxis.labels.fontSize = 6.5
    chart.categoryAxis.labels.angle = 25
    chart.categoryAxis.labels.dy = -10
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 100
    chart.valueAxis.valueSteps = [0, 25, 50, 75, 100]
    chart.valueAxis.labelTextFormat = '%d%%'
    chart.valueAxis.labels.fontSize = 7
    chart.bars[0].fillColor = BRAND_VIOLET
    chart.barWidth = 8
    chart.groupSpacing = 6
    # colour each bar by performance band
    for i, t in enumerate(topics):
        chart.bars[(0, i)].fillColor = _grade_color(t['average'])
    d.add(chart)

    legend = Legend()
    legend.x = chart.x
    legend.y = height - 0.25*cm
    legend.alignment = 'right'
    legend.fontSize = 6.5
    legend.dx = 6
    legend.dy = 6
    legend.deltax = 58
    legend.columnMaximum = 1
    legend.colorNamePairs = [
        (BRAND_GREEN, 'Strong (75%+)'),
        (BRAND_BLUE, 'Good (65-74%)'),
        (BRAND_AMBER, 'Fair (45-64%)'),
        (BRAND_ROSE, 'Needs support (<45%)'),
    ]
    d.add(legend)
    return d


STUDENT_COMPARE_COLORS = [BRAND_BLUE, BRAND_GREEN, BRAND_AMBER, BRAND_VIOLET, BRAND_ROSE, colors.HexColor('#06b6d4')]


def _multi_trend_chart(students, width=CHART_W, height=CHART_H) -> Drawing:
    """
    Overlays each student's exam-percentage trend on one chart, one
    color-coded line per student. Plotted by exam *sequence* (1st exam,
    2nd exam, ...) rather than calendar date, since two students being
    compared may have taken a different number of exams on different
    dates — sequence keeps the chart readable and still tells the
    "trajectory" story the comparison is for.

    `students` is [{'name': str, 'timeline': [{'percentage': ...}, ...],
    'color': a reportlab Color}, ...].
    """
    d = Drawing(width, height)
    max_len = max((len(s['timeline']) for s in students), default=0)
    if max_len < 2:
        d.add(String(width/2, height/2, 'Not enough exam data yet for a trend chart',
                      fontSize=9, fillColor=BRAND_GRAY, textAnchor='middle'))
        return d

    plot = LinePlot()
    plot.x = 1.6*cm
    plot.y = 1.3*cm
    plot.width = width - 2.6*cm
    plot.height = height - 2.0*cm
    plot.data = [list(enumerate(t['percentage'] for t in s['timeline'])) for s in students]

    for i, s in enumerate(students):
        plot.lines[i].strokeColor = s['color']
        plot.lines[i].strokeWidth = 1.8
        plot.lines[i].symbol = makeMarker('FilledCircle')
        plot.lines[i].symbol.fillColor = s['color']
        plot.lines[i].symbol.strokeColor = s['color']
        plot.lines[i].symbol.size = 3

    plot.xValueAxis.valueMin = 0
    plot.xValueAxis.valueMax = max_len - 1
    plot.xValueAxis.valueSteps = list(range(max_len))
    plot.xValueAxis.labelTextFormat = lambda v: f'#{int(v)+1}' if 0 <= int(v) < max_len else ''
    plot.xValueAxis.labels.fontSize = 7

    plot.yValueAxis.valueMin = 0
    plot.yValueAxis.valueMax = 100
    plot.yValueAxis.valueSteps = [0, 25, 50, 75, 100]
    plot.yValueAxis.labelTextFormat = '%d%%'
    plot.yValueAxis.labels.fontSize = 7

    d.add(plot)

    legend = Legend()
    legend.x = plot.x + 4
    legend.y = height - 0.15*cm
    legend.alignment = 'right'
    legend.fontSize = 7
    legend.dx = 7
    legend.dy = 7
    legend.deltax = 75
    legend.columnMaximum = 1
    legend.colorNamePairs = [(s['color'], s['name']) for s in students]
    d.add(legend)

    pass_y = plot.y + (50/100) * plot.height
    d.add(String(plot.x + plot.width - 0.1*cm, pass_y + 2, '50% pass mark',
                  fontSize=6, fillColor=BRAND_GRAY, textAnchor='end'))
    from reportlab.graphics.shapes import Line
    d.add(Line(plot.x, pass_y, plot.x + plot.width, pass_y,
               strokeColor=BRAND_AMBER, strokeWidth=0.5, strokeDashArray=[2, 2]))
    return d


def _multi_bar_chart(labels, series, width=CHART_W, height=CHART_H) -> Drawing:
    """
    Grouped bar chart comparing several students on the same set of
    categories (e.g. topics) — one color-coded bar cluster per category.
    `series` is [{'name': str, 'values': list[float], 'color': a
    reportlab Color}, ...], each `values` list aligned to `labels` (use
    0 for a student with no data on that category — reportlab bar charts
    can't skip slots, so a gap has to be an explicit zero, not a null).
    """
    d = Drawing(width, height)
    if not labels or not series:
        d.add(String(width/2, height/2, 'No comparable topic data available',
                      fontSize=9, fillColor=BRAND_GRAY, textAnchor='middle'))
        return d

    chart = VerticalBarChart()
    chart.x = 1.6*cm
    chart.y = 1.6*cm
    chart.width = width - 2.4*cm
    chart.height = height - 2.9*cm
    chart.data = [s['values'] for s in series]
    chart.categoryAxis.categoryNames = [
        (lbl[:12] + '…') if len(lbl) > 13 else lbl for lbl in labels
    ]
    chart.categoryAxis.labels.fontSize = 6.5
    chart.categoryAxis.labels.angle = 25
    chart.categoryAxis.labels.dy = -10
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 100
    chart.valueAxis.valueSteps = [0, 25, 50, 75, 100]
    chart.valueAxis.labelTextFormat = '%d%%'
    chart.valueAxis.labels.fontSize = 7
    for i, s in enumerate(series):
        chart.bars[i].fillColor = s['color']
    chart.barWidth = 6
    chart.groupSpacing = 10
    chart.barSpacing = 1
    d.add(chart)

    legend = Legend()
    legend.x = chart.x
    legend.y = height - 0.25*cm
    legend.alignment = 'right'
    legend.fontSize = 6.5
    legend.dx = 6
    legend.dy = 6
    legend.deltax = 68
    legend.columnMaximum = 1
    legend.colorNamePairs = [(s['color'], s['name']) for s in series]
    d.add(legend)
    return d


def generate_student_comparison_pdf(students_data, school_name='School of Excellence',
                                     subject_name=None) -> bytes:
    """
    Side-by-side comparison report for 2+ students — built for a teacher
    to print and hand to a student during a 1:1 conversation, so the tone
    stays constructive: it leads with each student's own growth (first
    exam -> most recent exam), not a blunt ranking.

    `students_data` is a list of dicts, one per student, each shaped like:
    {
      'name': str, 'student_code': str, 'classroom': str,
      'summary': {...} (from analytics.services.get_student_summary),
      'timeline': [...] (from analytics.services.get_student_trend),
      'topics': [...] (from analytics.services.get_student_topic_analysis),
      'growth': {'first_pct': float|None, 'last_pct': float|None, 'delta': float|None},
      'quiz_streak': int|None, 'badge_count': int|None,
    }
    Ordering of this list is preserved everywhere (colors, legend, table
    columns) — callers should already have it in the order they want
    displayed.
    """
    buf = io.BytesIO()
    styles = _make_styles()
    n = len(students_data)
    colored = [
        {**s, 'color': STUDENT_COMPARE_COLORS[i % len(STUDENT_COMPARE_COLORS)]}
        for i, s in enumerate(students_data)
    ]

    names_line = ' vs '.join(s['name'] for s in students_data)
    meta = {
        'school_name': school_name,
        'academic_year': '',
        'doc_title': 'Student Progress Comparison',
        'doc_subtitle': names_line + (f'  ·  {subject_name}' if subject_name else ''),
        'footer_centre': 'Confidential — for the named students and their teachers/guardians',
    }

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=4.2*cm, bottomMargin=2.2*cm,
    )
    story = []

    # ── Headline: each student's own growth story ───────────────────────
    intro = (
        "This report compares each student's own trajectory over time, side "
        "by side — the goal is to see how each of them is growing, and what "
        "each can learn from the other's approach."
    )
    story.append(Paragraph(intro, styles['body']))
    story.append(Spacer(1, 0.3*cm))

    grid_rows = [['', *[s['name'] for s in students_data]]]
    grid_rows.append(['Classroom', *[s.get('classroom') or '—' for s in students_data]])
    grid_rows.append(['Exams recorded', *[str(s['summary'].get('total_exams') or 0) for s in students_data]])
    grid_rows.append(['Overall average', *[
        f"{s['summary'].get('average_percentage')}%" if s['summary'].get('average_percentage') is not None else '—'
        for s in students_data
    ]])
    grid_rows.append(['Pass rate', *[
        f"{s['summary'].get('pass_rate')}%" if s['summary'].get('pass_rate') is not None else '—'
        for s in students_data
    ]])
    grid_rows.append(['Growth (first → latest exam)', *[
        (
            f"{s['growth']['first_pct']}% → {s['growth']['last_pct']}%  "
            f"({'+' if s['growth']['delta'] >= 0 else ''}{s['growth']['delta']} pts)"
        ) if s.get('growth') and s['growth'].get('delta') is not None else 'Not enough data yet'
        for s in students_data
    ]])
    if any(s.get('quiz_streak') is not None for s in students_data):
        grid_rows.append(['Current quiz streak', *[
            f"{s['quiz_streak']} days" if s.get('quiz_streak') is not None else '—' for s in students_data
        ]])
    if any(s.get('badge_count') is not None for s in students_data):
        grid_rows.append(['Badges earned', *[
            str(s.get('badge_count')) if s.get('badge_count') is not None else '—' for s in students_data
        ]])

    col_width = (PAGE_W - 2*MARGIN - 4.2*cm) / max(n, 1)
    gtbl = Table(grid_rows, colWidths=[4.2*cm] + [col_width] * n)
    gtbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.extend(_section_card('At a Glance', gtbl, styles))
    story.append(Spacer(1, 0.4*cm))

    # ── Trend overlay ────────────────────────────────────────────────────
    story.extend(_section_card(
        'Score Trend — Side by Side', _multi_trend_chart(colored), styles,
        caption='Each point is one exam, in the order that student took it (exam #1, #2, ...).',
    ))
    story.append(Spacer(1, 0.4*cm))

    # ── Topic comparison ─────────────────────────────────────────────────
    all_topic_names = []
    seen = set()
    for s in students_data:
        for t in s.get('topics', []):
            if t['topic_name'] not in seen:
                seen.add(t['topic_name'])
                all_topic_names.append(t['topic_name'])

    if all_topic_names:
        bar_series = []
        for s in colored:
            by_name = {t['topic_name']: t['average'] for t in s.get('topics', [])}
            bar_series.append({
                'name': s['name'], 'color': s['color'],
                'values': [by_name.get(name, 0) for name in all_topic_names],
            })
        story.extend(_section_card(
            'Topic Mastery — Side by Side', _multi_bar_chart(all_topic_names, bar_series), styles,
            caption='0% bars mean that student has no recorded data for that topic yet, not a zero score.',
        ))
    else:
        story.extend(_section_card(
            'Topic Mastery — Side by Side',
            Paragraph('No topic-tagged exam data recorded for these students yet.', styles['body']), styles,
        ))

    doc.build(story, onFirstPage=lambda c, d: _header_footer(c, d, meta),
              onLaterPages=lambda c, d: _header_footer(c, d, meta))
    return buf.getvalue()



    """Grouped bar chart: student's score vs classroom average, per exam.
    New chart — makes it possible to see at a glance whether the student is
    ahead of, in line with, or behind their classmates on each exam, not
    just their trend in isolation."""
    d = Drawing(width, height)
    if not labels:
        d.add(String(width/2, height/2, 'No classroom comparison data available',
                      fontSize=9, fillColor=BRAND_GRAY, textAnchor='middle'))
        return d

    chart = VerticalBarChart()
    chart.x = 1.6*cm
    chart.y = 1.6*cm
    chart.width = width - 2.4*cm
    chart.height = height - 2.9*cm
    chart.data = [student_vals, class_vals]
    chart.categoryAxis.categoryNames = [
        (lbl[:12] + '…') if len(lbl) > 13 else lbl for lbl in labels
    ]
    chart.categoryAxis.labels.fontSize = 6.5
    chart.categoryAxis.labels.angle = 25
    chart.categoryAxis.labels.dy = -10
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 100
    chart.valueAxis.valueSteps = [0, 25, 50, 75, 100]
    chart.valueAxis.labelTextFormat = '%d%%'
    chart.valueAxis.labels.fontSize = 7
    chart.bars[0].fillColor = BRAND_BLUE
    chart.bars[1].fillColor = BRAND_GRAY
    chart.barWidth = 6
    chart.groupSpacing = 10
    chart.barSpacing = 1
    d.add(chart)

    legend = Legend()
    legend.x = chart.x
    legend.y = height - 0.25*cm
    legend.alignment = 'right'
    legend.fontSize = 6.5
    legend.dx = 6
    legend.dy = 6
    legend.deltax = 60
    legend.columnMaximum = 1
    legend.colorNamePairs = [(BRAND_BLUE, 'This student'), (BRAND_GRAY, 'Classroom avg')]
    d.add(legend)
    return d


def _grade_distribution_pie(scores_present, width=8*cm, height=CHART_H) -> Drawing:
    """Pie chart of letter-grade distribution across all exams taken."""
    d = Drawing(width, height)
    if not scores_present:
        d.add(String(width/2, height/2, 'No graded exams yet',
                      fontSize=9, fillColor=BRAND_GRAY, textAnchor='middle'))
        return d

    counts = {}
    for s in scores_present:
        g = _letter_grade(s.percentage)
        counts[g] = counts.get(g, 0) + 1
    order = ['A', 'B', 'C', 'D', 'F']
    labels = [g for g in order if g in counts]
    values = [counts[g] for g in labels]
    grade_colors = {
        'A': BRAND_GREEN, 'B': BRAND_BLUE,
        'C': BRAND_AMBER, 'D': colors.HexColor('#fb923c'), 'F': BRAND_ROSE,
    }

    pie = Pie()
    pie.x = 0.3*cm
    pie.y = 0.4*cm
    pie.width = height - 0.8*cm
    pie.height = height - 0.8*cm
    pie.data = values
    pie.labels = [f'{g} ({c})' for g, c in zip(labels, values)]
    pie.simpleLabels = 0
    pie.sideLabels = 1
    pie.slices.strokeWidth = 0.5
    pie.slices.strokeColor = WHITE
    pie.slices.fontSize = 7
    for i, g in enumerate(labels):
        pie.slices[i].fillColor = grade_colors.get(g, BRAND_GRAY)
    d.add(pie)
    return d


def _section_card(title: str, drawing: Drawing, styles, width=None, caption: str = None) -> list:
    """Wrap a chart drawing with a section heading and optional explanatory
    caption inside a light card border."""
    items = [Paragraph(title, styles['section']), Spacer(1, 0.1*cm)]
    box_rows = [[drawing]]
    if caption:
        box_rows.append([Paragraph(caption, styles['caption'])])
    tbl = Table(box_rows, colWidths=[width or CHART_W])
    tbl.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    items.append(tbl)
    return items


def _honors_grid(badges, styles, width=None, per_row=3) -> Table:
    """A grid of badge medallions (icon + name + description + date), 3 per
    row by default. Used for both the exam-based student report and the
    quiz-progress report so every 'prizes won' listing looks identical."""
    width = width or (PAGE_W - 2*MARGIN)
    cell_w = width / per_row
    medal_style = ParagraphStyle('medal_name', fontSize=8.5, fontName='Helvetica-Bold',
                                  textColor=BRAND_DARK, leading=10)
    desc_style = ParagraphStyle('medal_desc', fontSize=7, fontName='Helvetica',
                                 textColor=BRAND_GRAY, leading=8.5)
    date_style = ParagraphStyle('medal_date', fontSize=6.5, fontName='Helvetica-Oblique',
                                 textColor=BRAND_GRAY, leading=8)

    rows, current = [], []
    for sb in badges:
        medallion = draw_badge_drawing(sb.badge.icon, size=30)
        cell = Table([
            [medallion, Paragraph(sb.badge.name, medal_style)],
            ['', Paragraph(sb.badge.description, desc_style)],
            ['', Paragraph(f'Earned {sb.awarded_at.strftime("%d %b %Y")}', date_style)],
        ], colWidths=[36, cell_w - 36])
        cell.setStyle(TableStyle([
            ('VALIGN', (0, 0), (0, 0), 'TOP'),
            ('SPAN', (0, 0), (0, 2)),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        current.append(cell)
        if len(current) == per_row:
            rows.append(current)
            current = []
    if current:
        while len(current) < per_row:
            current.append('')
        rows.append(current)

    grid = Table(rows, colWidths=[cell_w] * per_row)
    grid.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafafa')),
    ]))
    return grid


def _honors_achievements_section(styles, badges, tournament_stats=None, width=None) -> list:
    """'Honors & Achievements' block for the individual student report:
    badge medallion grid plus (when supplied) a tournament record strip —
    titles, duel wins, and rising-star call-outs. Never emitted empty:
    falls back to an encouraging placeholder so the section is consistent
    across every student's report."""
    items = [Paragraph('Honors &amp; Achievements', styles['section']), Spacer(1, 0.08*cm)]

    if tournament_stats and any(tournament_stats.get(k) for k in
                                 ('titles', 'match_wins', 'participations', 'rising_star_count')):
        ts = tournament_stats
        items.append(_meta_grid([
            ('TOURNAMENTS ENTERED', ts.get('participations') or 0),
            ('TOURNAMENT TITLES', ts.get('titles') or 0),
            ('DUEL WINS', ts.get('match_wins') or 0),
            ('RISING STAR MOMENTS', ts.get('rising_star_count') or 0),
        ], styles))
        items.append(Spacer(1, 0.25*cm))

    if badges:
        items.append(_honors_grid(badges, styles, width=width))
    else:
        items.append(Paragraph(
            'No badges earned yet — badges are awarded automatically for exam streaks, '
            'perfect scores, comebacks, and tournament performance.', styles['body'],
        ))
    return items


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
        ('AVERAGE', f'{avg}%' if present else '—'),
        ('PASS RATE', f'{pass_rate}%' if present else '—'),
        ('HIGHEST', f'{max(s.percentage for s in present)}%' if present else '—'),
        ('LOWEST', f'{min(s.percentage for s in present)}%' if present else '—'),
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

    col_w = [(PAGE_W - 2*MARGIN) * p for p in [0.05, 0.13, 0.22, 0.08, 0.10, 0.10, 0.10, 0.10, 0.12]]
    headers = ['#', 'ID', 'Student Name', 'Stream', 'Score', '%', 'Grade', 'Pass?', 'Remarks']
    table_data = [headers]

    for rank, s in enumerate(scores_list, 1):
        stream_name = s.student.stream.name if s.student.stream_id else '—'
        if s.is_absent:
            row = [str(rank), s.student.student_id, s.student.full_name, stream_name,
                   'ABSENT', '—', '—', '—', s.remarks or '']
        else:
            row = [
                str(rank),
                s.student.student_id,
                s.student.full_name,
                stream_name,
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
        ('ALIGN', (3,0), (7,-1), 'CENTER'),
    ]

    # Colour pass/fail column
    for i, s in enumerate(scores_list, 1):
        if not s.is_absent:
            color = BRAND_GREEN if s.passed else BRAND_ROSE
            row_styles.append(('TEXTCOLOR', (7, i), (7, i), color))
            row_styles.append(('FONTNAME', (7, i), (7, i), 'Helvetica-Bold'))

    tbl.setStyle(TableStyle(row_styles))
    story.append(tbl)

    doc.build(story, onFirstPage=lambda c, d: _header_footer(c, d, meta),
              onLaterPages=lambda c, d: _header_footer(c, d, meta))
    return buf.getvalue()


def generate_class_report_pdf(classroom, students, scores_map, exams,
                               sort_by='name', school_name='School of Excellence',
                               top_achievers=None) -> bytes:
    """
    Class performance report: one row per student, one column per exam.
    sort_by: 'name' | 'average_desc' | 'average_asc' | 'student_id'

    `top_achievers` — optional list of dicts (already ranked by the caller):
    [{'student': StudentProfile, 'badge_count': int, 'latest_badge': Badge|None}, ...]
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
    class_avg = round(sum(all_avgs) / len(all_avgs), 1) if all_avgs else None
    story.append(_meta_grid([
        ('CLASS', str(classroom.name)),
        ('GRADE LEVEL', classroom.grade_level.name),
        ('STUDENTS', len(students)),
        ('EXAMS', len(exams)),
        ('CLASS AVERAGE', f'{class_avg}%' if class_avg is not None else '—'),
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

    # ── Top Achievers (badge leaderboard) ───────────────────────────────────
    if top_achievers:
        story.append(Paragraph('Top Achievers', styles['section']))
        rows = [['Rank', 'Medal', 'Student', 'Badges Earned', 'Most Recent']]
        for i, row in enumerate(top_achievers[:5], 1):
            latest = row.get('latest_badge')
            medallion = draw_badge_drawing(latest.icon, size=22) if latest else ''
            rows.append([
                f'#{i}', medallion, row['student'].full_name,
                str(row['badge_count']), latest.name if latest else '—',
            ])
        ach_tbl = Table(rows, colWidths=[
            (PAGE_W - 2*MARGIN)*p for p in [0.08, 0.10, 0.42, 0.20, 0.20]
        ])
        ach_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, BRAND_LIGHT]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (1, -1), 'CENTER'),
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(ach_tbl)
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
    fixed_cols = 4  # rank, id, name, stream
    total_w = PAGE_W - 2*MARGIN
    fixed_w = total_w * 0.34
    exam_col_w = (total_w - fixed_w - total_w*0.08) / max(n, 1) if n else 1
    avg_w = total_w * 0.08

    col_widths = [total_w*0.04, total_w*0.09, total_w*0.14, total_w*0.07] + [exam_col_w]*n + [avg_w]
    headers = ['#', 'ID', 'Name', 'Stream'] + exam_headers + ['AVG']
    matrix = [headers]

    for rank, (s, student_scores, avg) in enumerate(rows_data, 1):
        row = [str(rank), s.student_id, s.full_name, s.stream.name if s.stream_id else '—']
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
                                 school_name='School of Excellence',
                                 trend=None, comparison=None,
                                 badges=None, tournament_stats=None) -> bytes:
    """
    Full individual student analytics report (A4).

    Includes: profile summary, honors & achievements (badges + tournament
    record), score trend chart (with classroom-average overlay), topic
    mastery bar chart (with a colour-band legend), grade distribution pie
    chart, a student-vs-classroom comparison chart, class rank/percentile,
    term-by-term breakdown, full examination history (with classroom
    average per exam), topic mastery table, and an auto-generated
    strengths/watch-areas narrative.

    `badges` — optional list of gamification.models.StudentBadge (already
    fetched/ordered by the caller). `tournament_stats` — optional dict with
    keys participations/titles/match_wins/rising_star_count.
    """
    buf = io.BytesIO()
    styles = _make_styles()
    scores = list(scores)
    trend = trend or {}
    comparison = comparison or {}
    class_by_exam = comparison.get('by_exam') or {}
    rank = comparison.get('rank')
    class_size = comparison.get('class_size') or 0
    percentile = comparison.get('percentile')

    present = [s for s in scores if not s.is_absent]
    pcts = [s.percentage for s in present]
    avg = round(sum(pcts) / len(pcts), 1) if pcts else 0
    passed_count = sum(1 for s in present if s.passed)
    highest = max(pcts) if pcts else 0
    lowest = min(pcts) if pcts else 0
    consistency = round(_std_dev_pdf(pcts), 1) if len(pcts) > 1 else 0
    trend_label = (trend.get('trend') or 'no_data').replace('_', ' ').capitalize()

    meta = {
        'school_name': school_name,
        'academic_year': scores[0].exam.academic_year if scores else '—',
        'doc_title': f'Individual Student Report — {student.full_name}',
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

    # ── Summary metrics ──────────────────────────────────────────────────────
    # NOTE: when a student has no non-absent scores (pcts is empty), avg/
    # highest/lowest are computed as 0 above purely to avoid a ZeroDivision
    # — they don't represent a real 0% score. Render '—' for those fields in
    # that case instead of a misleading "0%" (PREDICTED GRADE already did
    # this correctly; the other four fields did not).
    story.append(_meta_grid([
        ('STUDENT', student.full_name),
        ('STUDENT ID', student.student_id),
        ('CLASSROOM', str(student.classroom) if student.classroom else '—'),
        ('EXAMS TAKEN', len(present)),
        ('OVERALL AVG', f'{avg}%' if pcts else '—'),
        ('PASS RATE', f'{round(passed_count/len(present)*100, 1)}%' if present else '—'),
    ], styles))
    story.append(Spacer(1, 0.25*cm))
    story.append(_meta_grid([
        ('HIGHEST SCORE', f'{highest}%' if pcts else '—'),
        ('LOWEST SCORE', f'{lowest}%' if pcts else '—'),
        ('CONSISTENCY (σ)', f'{consistency} pts'),
        ('PERFORMANCE TREND', trend_label),
        ('EXAMS PASSED', f'{passed_count}/{len(present)}'),
        ('PREDICTED GRADE', _letter_grade(avg) if pcts else '—'),
    ], styles))
    story.append(Spacer(1, 0.25*cm))
    story.append(_meta_grid([
        ('CLASS RANK', f'{rank} of {class_size}' if rank else '—'),
        ('CLASS PERCENTILE', f'Top {round(100 - percentile, 1)}%' if percentile is not None else '—'),
        ('CLASSMATES COMPARED', str(class_size) if class_size else '—'),
    ], styles))
    story.append(Spacer(1, 0.45*cm))

    # ── Honors & Achievements (badges + tournament record) ────────────────
    story.extend(_honors_achievements_section(styles, badges or [], tournament_stats))
    story.append(Spacer(1, 0.4*cm))

    # ── Score trend chart ────────────────────────────────────────────────────
    timeline = trend.get('timeline') or [
        {'exam_date': s.exam.exam_date.strftime('%Y-%m-%d'), 'percentage': s.percentage}
        for s in present
    ]
    class_series = None
    if class_by_exam and trend.get('timeline'):
        class_series = [class_by_exam.get(t['exam_id']) for t in trend['timeline']]
    story.extend(_section_card(
        'Score Trend Over Time',
        _trend_chart(timeline, trend.get('moving_average'), class_avg_series=class_series), styles,
        caption=(
            'Each point is one exam\'s score. The dashed violet line is a 3-exam moving '
            'average (smooths out one-off high/low results); the dashed grey line is the '
            'classroom average on those same exams, when available, so you can see whether '
            'the student is pulling ahead of, keeping pace with, or falling behind the class.'
        ),
    ))
    story.append(Spacer(1, 0.4*cm))

    # ── Topic mastery + grade distribution side-by-side ─────────────────────
    half_w = (PAGE_W - 2*MARGIN - 0.4*cm) / 2
    topic_drawing = _topic_bar_chart(topic_data, width=half_w)
    pie_drawing = _grade_distribution_pie(present, width=half_w)
    two_col = Table(
        [[
            Table([[Paragraph('Topic Mastery', styles['section'])], [topic_drawing],
                   [Paragraph('Bars are colour-banded by average score — see legend on the chart.', styles['caption'])]],
                  colWidths=[half_w]),
            Table([[Paragraph('Grade Distribution', styles['section'])], [pie_drawing],
                   [Paragraph('Share of exams (not topics) falling in each letter-grade band.', styles['caption'])]],
                  colWidths=[half_w]),
        ]],
        colWidths=[half_w, half_w],
    )
    two_col.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (1,0), (1,0), 8),
    ]))
    story.append(two_col)
    story.append(Spacer(1, 0.4*cm))

    # ── Student vs classroom average, per exam ───────────────────────────────
    if class_by_exam and trend.get('timeline'):
        cmp_timeline = [t for t in trend['timeline'] if t['exam_id'] in class_by_exam]
        if cmp_timeline:
            labels = [t['exam_title'] for t in cmp_timeline]
            student_vals = [t['percentage'] for t in cmp_timeline]
            class_vals = [class_by_exam[t['exam_id']] for t in cmp_timeline]
            story.extend(_section_card(
                'Student vs. Classroom Average — Per Exam',
                _multi_bar_chart(labels, [
                    {'name': student.full_name, 'values': student_vals, 'color': BRAND_BLUE},
                    {'name': 'Classroom Average', 'values': class_vals, 'color': BRAND_GRAY},
                ]), styles,
                caption=(
                    'Blue bars are this student\'s score; grey bars are the classroom average '
                    'on the same exam. Blue taller than grey means the student outperformed '
                    'the class average on that exam.'
                ),
            ))
            story.append(Spacer(1, 0.4*cm))

    # ── Term-by-term breakdown ───────────────────────────────────────────────
    term_groups = {}
    term_labels = {}
    for s in present:
        key = (s.exam.academic_year, s.exam.term)
        term_groups.setdefault(key, []).append(s.percentage)
        term_labels[key] = s.exam.get_term_display()
    if term_groups:
        story.append(Paragraph('Term-by-Term Performance', styles['section']))
        term_rows = [['Academic Year', 'Term', 'Exams', 'Average', 'Highest', 'Lowest']]
        for (year, term), vals in sorted(term_groups.items()):
            term_rows.append([
                year, term_labels[(year, term)], str(len(vals)),
                f'{round(sum(vals)/len(vals), 1)}%', f'{max(vals)}%', f'{min(vals)}%',
            ])
        term_tbl = Table(term_rows,
                          colWidths=[(PAGE_W-2*MARGIN)*p for p in [0.22, 0.22, 0.14, 0.14, 0.14, 0.14]],
                          repeatRows=1)
        term_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), BRAND_BLUE),
            ('TEXTCOLOR', (0,0), (-1,0), WHITE),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, BRAND_LIGHT]),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#e5e7eb')),
            ('ALIGN', (2,0), (-1,-1), 'CENTER'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(term_tbl)
        story.append(Spacer(1, 0.4*cm))

    # ── Strengths & watch areas (auto-generated narrative) ───────────────────
    if topic_data or class_by_exam:
        sorted_topics = sorted(topic_data, key=lambda t: t['average'], reverse=True)
        strong = [t['topic_name'] for t in sorted_topics if t['average'] >= 70][:3]
        weak = [t['topic_name'] for t in sorted_topics if t['average'] < 50][:3]
        narrative = []
        if strong:
            narrative.append(f"<b>Strengths:</b> Performing strongly in {', '.join(strong)}.")
        if weak:
            narrative.append(f"<b>Watch areas:</b> Needs support in {', '.join(weak)}.")
        if not strong and not weak and topic_data:
            narrative.append('Performance is fairly even across topics — no standout strengths or weak spots yet.')
        narrative.append(
            f"Overall trend is <b>{trend_label.lower()}</b> with a consistency score of "
            f"{consistency} percentage points (lower = more consistent)."
        )
        if rank and class_size:
            narrative.append(
                f"Currently ranked <b>{rank} of {class_size}</b> in class "
                f"({'top' if percentile and percentile >= 50 else 'bottom'} "
                f"{round(percentile if percentile and percentile >= 50 else 100 - (percentile or 0), 1)}%)."
            )
        story.append(Paragraph('Performance Insights', styles['section']))
        story.append(Paragraph('<br/>'.join(narrative), styles['body']))
        story.append(Spacer(1, 0.4*cm))

    story.append(PageBreak())

    # ── Full examination history ─────────────────────────────────────────────
    story.append(Paragraph('Full Examination History', styles['section']))
    story.append(Paragraph(
        '"Class Avg" is the classroom average on that same exam (when available); "vs Class" '
        'is this student\'s score minus that average — positive means above the class average.',
        styles['caption'],
    ))
    has_cmp = bool(class_by_exam)
    if has_cmp:
        col_w = [(PAGE_W - 2*MARGIN)*p for p in [0.03, 0.26, 0.11, 0.10, 0.08, 0.07, 0.07, 0.06, 0.07, 0.08, 0.07]]
        tbl_data = [['#', 'Exam', 'Type', 'Date', 'Score', '%', 'Class Avg', 'vs Class', 'Grade', 'Pass?', '']]
    else:
        col_w = [(PAGE_W - 2*MARGIN)*p for p in [0.04, 0.34, 0.13, 0.13, 0.10, 0.10, 0.08, 0.08]]
        tbl_data = [['#', 'Exam', 'Type', 'Date', 'Score', '%', 'Grade', 'Pass?']]
    for i, s in enumerate(scores, 1):
        if s.is_absent:
            row = [str(i), s.exam.title, s.exam.get_exam_type_display(),
                   s.exam.exam_date.strftime('%d %b %Y'), 'ABSENT', '—']
            row += (['—', '—'] if has_cmp else [])
            row += ['—', '—']
            row += ([''] if has_cmp else [])
        else:
            row = [
                str(i), s.exam.title, s.exam.get_exam_type_display(),
                s.exam.exam_date.strftime('%d %b %Y'),
                f'{float(s.score):.1f}', f'{s.percentage}%',
            ]
            if has_cmp:
                cavg = class_by_exam.get(s.exam_id)
                diff = round(s.percentage - cavg, 1) if cavg is not None else None
                row += [f'{cavg}%' if cavg is not None else '—',
                        f'{"+" if diff is not None and diff > 0 else ""}{diff}%' if diff is not None else '—']
            row += [s.letter_grade, '✓' if s.passed else '✗']
            row += ([''] if has_cmp else [])
        tbl_data.append(row if has_cmp else row[:8])

    tbl = Table(tbl_data, colWidths=col_w, repeatRows=1)
    pass_col = 9 if has_cmp else 7
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
            tstyles.append(('TEXTCOLOR', (pass_col, i), (pass_col, i), tbl_styles_color))
            tstyles.append(('FONTNAME', (pass_col, i), (pass_col, i), 'Helvetica-Bold'))
            if has_cmp:
                cavg = class_by_exam.get(s.exam_id)
                if cavg is not None:
                    diff_color = BRAND_GREEN if s.percentage >= cavg else BRAND_ROSE
                    tstyles.append(('TEXTCOLOR', (7, i), (7, i), diff_color))
    tbl.setStyle(TableStyle(tstyles))
    story.append(tbl)

    # ── Topic mastery table ──────────────────────────────────────────────────
    if topic_data:
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph('Topic Mastery — Detail', styles['section']))
        topic_rows = [['Topic', 'Average %', 'Grade', 'Attempts', 'Highest', 'Lowest', 'Trend']]
        for t in topic_data:
            topic_rows.append([
                t['topic_name'],
                f"{t['average']}%",
                _letter_grade(t['average']),
                str(t['attempts']),
                f"{t.get('highest', '—')}%",
                f"{t.get('lowest', '—')}%",
                t['trend'].capitalize(),
            ])
        ttbl = Table(topic_rows,
                     colWidths=[(PAGE_W-2*MARGIN)*p for p in [0.30, 0.13, 0.10, 0.12, 0.12, 0.12, 0.11]],
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


def generate_quiz_progress_pdf(student, progress, streak, badges,
                                school_name='School of Excellence') -> bytes:
    """
    Daily-quiz progress report (A4) for one student: summary metrics,
    quiz streak, earned badges, score trend, and topic-mastery breakdown.
    Reuses the same chart/section helpers as generate_student_report_pdf
    so the two report types read as one consistent family of documents.

    `progress` is the dict returned by
    quizzes.analytics_services.get_student_quiz_topic_progress()
    (keys: summary, timeline, moving_average, topic_data).
    `streak` is a gamification.models.QuizStreak instance.
    `badges` is a list of gamification.models.StudentBadge instances
    (already filtered to quiz-related badges by the caller).
    """
    buf = io.BytesIO()
    styles = _make_styles()
    summary = progress.get('summary') or {}
    timeline = progress.get('timeline') or []
    topic_data = progress.get('topic_data') or []

    quizzes_taken = summary.get('quizzes_taken') or 0
    avg = summary.get('average')
    trend_label = (summary.get('trend') or 'no_data').replace('_', ' ').capitalize()

    meta = {
        'school_name': school_name,
        'academic_year': timeline[-1]['exam_date'][:4] if timeline else '—',
        'doc_title': f'Daily Quiz Progress Report — {student.full_name}',
        'doc_subtitle': (
            f'Student ID: {student.student_id}  ·  '
            f'Class: {student.classroom or "—"}'
        ),
        'footer_centre': f'Student ID: {student.student_id}',
    }

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=4.2*cm, bottomMargin=2.2*cm,
    )
    story = []

    # ── Summary metrics ──────────────────────────────────────────────────
    story.append(_meta_grid([
        ('STUDENT', student.full_name),
        ('STUDENT ID', student.student_id),
        ('CLASSROOM', str(student.classroom) if student.classroom else '—'),
        ('QUIZZES TAKEN', quizzes_taken),
        ('OVERALL AVG', f'{avg}%' if avg is not None else '—'),
        ('PASS RATE', f'{summary.get("pass_rate")}%' if summary.get('pass_rate') is not None else '—'),
    ], styles))
    story.append(Spacer(1, 0.25*cm))
    story.append(_meta_grid([
        ('HIGHEST SCORE', f'{summary.get("highest")}%' if summary.get('highest') is not None else '—'),
        ('LOWEST SCORE', f'{summary.get("lowest")}%' if summary.get('lowest') is not None else '—'),
        ('PERFORMANCE TREND', trend_label),
        ('CURRENT QUIZ STREAK', f'{streak.current_streak} 🔥' if streak else '—'),
        ('LONGEST QUIZ STREAK', str(streak.longest_streak) if streak else '—'),
        ('BADGES EARNED', str(len(badges))),
    ], styles))
    story.append(Spacer(1, 0.45*cm))

    # ── Badges ────────────────────────────────────────────────────────────
    if badges:
        story.extend(_section_card(
            'Badges Earned', _honors_grid(badges, styles, width=PAGE_W - 2*MARGIN), styles,
            caption='Awarded automatically for quiz consistency and standout scores.',
            width=PAGE_W - 2*MARGIN,
        ))
    else:
        story.extend(_section_card(
            'Badges Earned', Paragraph('No badges earned yet — keep up the daily quizzes!', styles['body']), styles,
        ))
    story.append(Spacer(1, 0.4*cm))

    # ── Score trend chart ────────────────────────────────────────────────
    if timeline:
        story.extend(_section_card(
            'Quiz Score Trend Over Time',
            _trend_chart(timeline, progress.get('moving_average')), styles,
            caption=(
                'Each point is one quiz\'s score. The dashed violet line is a 3-quiz '
                'moving average, smoothing out one-off high/low results.'
            ),
        ))
        story.append(Spacer(1, 0.4*cm))

    # ── Topic mastery ─────────────────────────────────────────────────────
    if topic_data:
        story.extend(_section_card(
            'Topic Mastery', _topic_bar_chart(topic_data, width=PAGE_W - 2*MARGIN), styles,
            caption='Average score per topic across every daily quiz recorded on that topic.',
        ))
        story.append(Spacer(1, 0.3*cm))

        rows = [['Topic', 'Quizzes', 'Average', 'Highest', 'Lowest', 'Trend']]
        for t in topic_data:
            rows.append([
                t['topic_name'], str(t['attempts']), f"{t['average']}%",
                f"{t['highest']}%", f"{t['lowest']}%", t['trend'].capitalize(),
            ])
        ttbl = Table(rows, colWidths=[
            PAGE_W - 2*MARGIN - 2.2*cm*4 - 2.6*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.6*cm,
        ])
        ttbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(ttbl)
    else:
        story.extend(_section_card(
            'Topic Mastery', Paragraph('No topic-tagged quizzes recorded yet.', styles['body']), styles,
        ))

    doc.build(story, onFirstPage=lambda c, d: _header_footer(c, d, meta),
              onLaterPages=lambda c, d: _header_footer(c, d, meta))
    return buf.getvalue()


def _std_dev_pdf(values):
    if len(values) < 2:
        return 0
    m = sum(values) / len(values)
    return (sum((v - m) ** 2 for v in values) / len(values)) ** 0.5


def generate_at_risk_pdf(students, meta: dict, sort_by='score_asc', school_name='School of Excellence') -> bytes:
    """
    Generate a PDF export of at-risk students.
    students: list of dicts shaped like analytics.services.get_at_risk_students() output
              (student_id, student_name, student_code, classroom, recent_average,
               recent_scores, flags{below_threshold, declining}).
    sort_by: 'score_asc' (most at risk first) | 'score_desc' | 'name' | 'classroom'
    """
    sort_map = {
        'score_asc':  lambda s: s['recent_average'],
        'score_desc': lambda s: -s['recent_average'],
        'name':       lambda s: s['student_name'].lower(),
        'classroom':  lambda s: (s['classroom'] or '').lower(),
    }
    rows = sorted(students, key=sort_map.get(sort_by, sort_map['score_asc']))

    buf = io.BytesIO()
    styles = _make_styles()

    threshold = meta.get('threshold')
    doc_meta = {
        'school_name': school_name,
        'academic_year': meta.get('academic_year', ''),
        'doc_title': 'At-Risk Students Report',
        'doc_subtitle': (
            f"Scope: {meta.get('scope_label', 'All Classrooms')}  ·  "
            f"Pass Threshold: {threshold}%  ·  "
            f"Flagged: {len(rows)} student{'s' if len(rows) != 1 else ''}"
        ),
        'footer_centre': 'At-Risk Students · Analytics',
    }

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=4.2*cm, bottomMargin=2.2*cm,
    )

    story = []

    # ── Summary stats ────────────────────────────────────────────────────────
    below = sum(1 for s in rows if s['flags']['below_threshold'])
    declining = sum(1 for s in rows if s['flags']['declining'])
    avg = round(sum(s['recent_average'] for s in rows) / len(rows), 1) if rows else 0

    summary_items = [
        ('FLAGGED', len(rows)),
        ('BELOW THRESHOLD', below),
        ('DECLINING', declining),
        ('AVERAGE SCORE', f'{avg}%' if rows else '—'),
    ]
    story.append(_meta_grid(summary_items, styles))
    story.append(Spacer(1, 0.4*cm))

    # ── Students table ───────────────────────────────────────────────────────
    sort_label = {
        'score_asc': 'Sorted by Recent Average (Lowest → Highest)',
        'score_desc': 'Sorted by Recent Average (Highest → Lowest)',
        'name': 'Sorted by Name',
        'classroom': 'Sorted by Classroom',
    }.get(sort_by, '')

    story.append(Paragraph(
        f'Flagged Students  <font color="#6b7280" size="8">({sort_label})</font>',
        styles['section'],
    ))

    if not rows:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph('No students are currently flagged as at-risk for this scope.', styles['body']))
    else:
        col_w = [(PAGE_W - 2*MARGIN) * p for p in [0.05, 0.13, 0.24, 0.18, 0.11, 0.14, 0.15]]
        headers = ['#', 'ID', 'Student Name', 'Classroom', 'Avg %', 'Trend', 'Flags']
        table_data = [headers]

        for rank, s in enumerate(rows, 1):
            scores = s['recent_scores']
            trend = ' → '.join(str(p) for p in reversed(scores)) if scores else '—'
            flags = []
            if s['flags']['below_threshold']:
                flags.append(f'Below {threshold}%')
            if s['flags']['declining']:
                flags.append('Declining')
            table_data.append([
                str(rank),
                s['student_code'],
                s['student_name'],
                s['classroom'] or '—',
                f"{s['recent_average']}%",
                trend,
                ', '.join(flags) if flags else '—',
            ])

        tbl = Table(table_data, colWidths=col_w, repeatRows=1)

        row_styles = [
            ('BACKGROUND', (0,0), (-1,0), BRAND_ROSE),
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
            ('ALIGN', (4,0), (4,-1), 'CENTER'),
            ('FONTSIZE', (5,1), (5,-1), 7),
        ]

        # Colour the average column by risk severity
        for i, s in enumerate(rows, 1):
            row_styles.append(('TEXTCOLOR', (4, i), (4, i), _grade_color(s['recent_average'])))
            row_styles.append(('FONTNAME', (4, i), (4, i), 'Helvetica-Bold'))

def _score_distribution_chart(distribution, width=CHART_W, height=CHART_H) -> Drawing:
    """Histogram of entrant scores across the 5 standard bands — the
    tournament dossier's 'shape of the field' visual."""
    d = Drawing(width, height)
    total = sum(b['count'] for b in distribution)
    if not distribution or total == 0:
        d.add(String(width/2, height/2, 'No scored entrants yet',
                      fontSize=9, fillColor=BRAND_GRAY, textAnchor='middle'))
        return d

    chart = VerticalBarChart()
    chart.x = 1.6*cm
    chart.y = 1.4*cm
    chart.width = width - 2.4*cm
    chart.height = height - 2.4*cm
    chart.data = [[b['count'] for b in distribution]]
    chart.categoryAxis.categoryNames = [f"{b['band']}%" for b in distribution]
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontSize = 7.5
    band_colors = [BRAND_ROSE, BRAND_AMBER, BRAND_BLUE, BRAND_GREEN, BRAND_VIOLET]
    for i in range(len(distribution)):
        chart.bars[(0, i)].fillColor = band_colors[i % len(band_colors)]
    chart.barWidth = 16
    chart.groupSpacing = 10
    d.add(chart)
    return d


def generate_tournament_dossier_pdf(tournament, dossier, analytics,
                                     school_name='School of Excellence') -> bytes:
    """
    FBI/CIA-style intel dossier for one finalized tournament: leaderboard
    with rank/score/delta, score distribution histogram, participation and
    pass-rate metrics vs. the whole classroom, champion + rising-star
    callouts (with real badge medallions), closest-duel/biggest-upset
    highlights, and the full challenge (duel) log.

    `dossier` — output of tournaments.services.get_tournament_dossier().
    `analytics` — output of tournaments.services.get_tournament_analytics().
    """
    buf = io.BytesIO()
    styles = _make_styles()
    results = dossier['results']
    champion = dossier['champion']
    rising_stars = dossier['rising_stars']
    challenges = tournament.challenges.prefetch_related('entries__student', 'entries__stream').select_related('winner').all()

    meta = {
        'school_name': school_name,
        'academic_year': tournament.exam.academic_year,
        'doc_title': f'Tournament Dossier — {tournament.title}',
        'doc_subtitle': (
            (f'Codename: {tournament.codename}  ·  ' if tournament.codename else '') +
            f'{tournament.get_mode_display()}  ·  {tournament.classroom}  ·  Decisive exam: {tournament.exam.title}'
        ),
        'footer_centre': f'Classroom: {tournament.classroom}',
    }

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=4.2*cm, bottomMargin=2.2*cm,
    )
    story = []

    # ── Summary metrics ──────────────────────────────────────────────────
    story.append(_meta_grid([
        ('STATUS', tournament.get_status_display()),
        ('ENTRANTS', analytics['entrant_count']),
        ('PARTICIPATION', f"{analytics['participation_rate']}%" if analytics['participation_rate'] is not None else '—'),
        ('PASS RATE', f"{analytics['pass_rate']}%" if analytics['pass_rate'] is not None else '—'),
        ('DUELS FOUGHT', challenges.count()),
    ], styles))
    story.append(Spacer(1, 0.25*cm))
    story.append(_meta_grid([
        ('ENTRANT AVERAGE', f"{analytics['entrant_average']}%" if analytics['entrant_average'] is not None else '—'),
        ('CLASSROOM AVERAGE', f"{analytics['classroom_average']}%" if analytics['classroom_average'] is not None else '—'),
        ('ABSENTEES', analytics['absentee_count']),
        ('DECISIVE EXAM', tournament.exam.title),
        ('EXAM DATE', str(tournament.exam.exam_date)),
    ], styles))
    story.append(Spacer(1, 0.45*cm))

    # ── Champion & Rising Stars callout ─────────────────────────────────
    if champion or rising_stars:
        callout_rows = []
        if champion:
            medallion = draw_badge_drawing('trophy', size=28)
            callout_rows.append([
                medallion,
                Paragraph(f'<b>Champion — {champion.entry.display_name}</b><br/>'
                          f'Finished #1 overall at {champion.score_percentage}%.', styles['body']),
            ])
        for r in rising_stars[:4]:
            medallion = draw_badge_drawing('sparkles', size=24)
            callout_rows.append([
                medallion,
                Paragraph(f'<b>Rising Star — {r.entry.display_name}</b><br/>'
                          f'Scored {r.score_percentage}%, up {r.delta:+.1f} pts on their own prior average.',
                          styles['body']),
            ])
        callout_tbl = Table(callout_rows, colWidths=[38, PAGE_W - 2*MARGIN - 38])
        callout_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
            ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#f3f4f6')),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffbeb')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(Paragraph('Champion &amp; Rising Stars', styles['section']))
        story.append(callout_tbl)
        story.append(Spacer(1, 0.4*cm))

    # ── Headline callouts (closest duel, biggest upset) ─────────────────
    headlines = []
    if analytics.get('closest_duel'):
        cd = analytics['closest_duel']
        headlines.append(f"Closest duel: <b>{cd['label'] or 'Unlabeled'}</b> — decided by just {cd['gap']} points.")
    if analytics.get('biggest_upset'):
        bu = analytics['biggest_upset']
        headlines.append(f"Biggest upset: <b>{bu['winner']}</b> won as the {bu['seed_gap']}-point underdog in \"{bu['label'] or 'a duel'}\".")
    if analytics.get('top_riser'):
        tr = analytics['top_riser']
        headlines.append(f"Sharpest rise: <b>{tr['name']}</b>, up {tr['delta']:+.1f} points on their own average.")
    if headlines:
        story.append(Paragraph('Field Intelligence', styles['section']))
        for h in headlines:
            story.append(Paragraph(f'• {h}', styles['body']))
        story.append(Spacer(1, 0.4*cm))

    # ── Score distribution ────────────────────────────────────────────────
    story.extend(_section_card(
        'Score Distribution', _score_distribution_chart(analytics['score_distribution']), styles,
        caption='How the field of entrants scored on the decisive exam, banded into 5 ranges.',
    ))
    story.append(Spacer(1, 0.4*cm))

    # ── Leaderboard ───────────────────────────────────────────────────────
    if results:
        story.append(Paragraph('Final Leaderboard', styles['section']))
        rows = [['Rank', 'Entrant', 'Score', 'Prior Avg', 'Change', 'Flags']]
        for r in results:
            flags = []
            if r.is_champion: flags.append('Champion')
            if r.is_rising_star: flags.append('Rising Star')
            if r.is_absent: flags.append('Absent')
            rows.append([
                f'#{r.rank}' if r.rank else '—',
                r.entry.display_name,
                f'{r.score_percentage}%' if r.score_percentage is not None else '—',
                f'{r.prior_average}%' if r.prior_average is not None else '—',
                f'{r.delta:+.1f}' if r.delta is not None else '—',
                ', '.join(flags) or '—',
            ])
        lb_tbl = Table(rows, colWidths=[(PAGE_W - 2*MARGIN)*p for p in [0.09, 0.32, 0.14, 0.14, 0.11, 0.20]])
        lb_style = [
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (4, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]
        for i, r in enumerate(results, 1):
            if r.is_champion:
                lb_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fef3c7')))
        lb_tbl.setStyle(TableStyle(lb_style))
        story.append(lb_tbl)
        story.append(Spacer(1, 0.4*cm))

    # ── Challenge log ─────────────────────────────────────────────────────
    challenge_list = list(challenges)
    if challenge_list:
        story.append(Paragraph('Challenge Log', styles['section']))
        rows = [['Duel', 'Combatants', 'Result', 'Status']]
        for c in challenge_list:
            names = ' vs '.join(e.display_name for e in c.entries.all())
            result = c.winner.display_name if c.winner else ('Tied' if c.is_tie else '—')
            rows.append([c.label or f'Duel #{c.id}', names, result, c.get_status_display()])
        ch_tbl = Table(rows, colWidths=[(PAGE_W - 2*MARGIN)*p for p in [0.22, 0.42, 0.22, 0.14]])
        ch_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(ch_tbl)

    doc.build(story, onFirstPage=lambda c, d: _header_footer(c, d, meta),
              onLaterPages=lambda c, d: _header_footer(c, d, meta))
    return buf.getvalue()


def generate_hall_of_fame_pdf(hof, *, scope_label='All Classrooms',
                               school_name='School of Excellence', academic_year='') -> bytes:
    """
    The league Hall of Fame export: current top-tier standings across every
    active/archived season in scope, the reigning champion of each season,
    and the all-time "most promoted" leaderboard. `hof` is the output of
    leagues.services.get_hall_of_fame().
    """
    buf = io.BytesIO()
    styles = _make_styles()

    meta = {
        'school_name': school_name,
        'academic_year': academic_year,
        'doc_title': 'League Hall of Fame',
        'doc_subtitle': f'Scope: {scope_label}',
        'footer_centre': 'League System',
    }

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=4.2*cm, bottomMargin=2.2*cm,
    )
    story = []

    top_tier = hof.get('top_tier', [])
    champions = hof.get('season_champions', [])
    most_promoted = hof.get('most_promoted', [])

    story.append(_meta_grid([
        ('TOP-TIER STUDENTS', len(top_tier)),
        ('SEASONS REPRESENTED', len(champions)),
        ('TRACKED CLIMBERS', len(most_promoted)),
    ], styles))
    story.append(Spacer(1, 0.45*cm))

    # ── Reigning Champions ────────────────────────────────────────────────
    if champions:
        story.append(Paragraph('Reigning Champions', styles['section']))
        callout_rows = []
        for c in champions[:8]:
            medallion = draw_badge_drawing('crown', size=24)
            callout_rows.append([
                medallion,
                Paragraph(
                    f"<b>{c['student_name']}</b> — {c['season_title']} ({c['classroom']})<br/>"
                    f"Top of \"{c['group_name']}\" at {c['score']}%.",
                    styles['body'],
                ),
            ])
        champ_tbl = Table(callout_rows, colWidths=[32, PAGE_W - 2*MARGIN - 32])
        champ_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
            ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#f3f4f6')),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fffbeb')),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(champ_tbl)
        story.append(Spacer(1, 0.4*cm))

    # ── Top-Tier Standings ───────────────────────────────────────────────
    if top_tier:
        story.append(Paragraph('Top-Tier Standings', styles['section']))
        rows = [['#', 'Student', 'Classroom', 'Season', 'Band', 'Score']]
        for i, row in enumerate(top_tier, 1):
            rows.append([
                str(i), row['student_name'], row['classroom'], row['season_title'],
                row['group_name'], f"{row['score']}%" if row['score'] is not None else '—',
            ])
        tbl = Table(rows, colWidths=[(PAGE_W - 2*MARGIN)*p for p in [0.06, 0.26, 0.18, 0.22, 0.16, 0.12]])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (5, 0), (5, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.4*cm))

    # ── Most Promoted ────────────────────────────────────────────────────
    if most_promoted:
        story.append(Paragraph('Most Promoted', styles['section']))
        rows = [['#', 'Student', 'Total Promotions']]
        for i, row in enumerate(most_promoted, 1):
            rows.append([str(i), row['student_name'], str(row['promotion_count'])])
        tbl2 = Table(rows, colWidths=[(PAGE_W - 2*MARGIN)*p for p in [0.1, 0.6, 0.3]])
        tbl2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(tbl2)

    if not (top_tier or champions or most_promoted):
        story.append(Paragraph('No league data yet for this scope.', styles['body']))

    doc.build(story, onFirstPage=lambda c, d: _header_footer(c, d, meta),
              onLaterPages=lambda c, d: _header_footer(c, d, meta))
    return buf.getvalue()
