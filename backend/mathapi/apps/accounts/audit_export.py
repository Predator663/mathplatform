"""
PDF "card" export engine for the audit log — a single richly-formatted
card per log entry (full diff included), either one at a time or as a
capped batch. Kept self-contained (own branding constants) rather than
importing mathapi.apps.reports, matching how mathapi.apps.groups.report_engine
already keeps its own copy rather than taking a cross-app dependency.
"""
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether, PageBreak, HRFlowable,
)

BRAND_BLUE  = colors.HexColor('#2563eb')
BRAND_DARK  = colors.HexColor('#0a0a0f')
BRAND_GRAY  = colors.HexColor('#6b7280')
BRAND_LIGHT = colors.HexColor('#f3f4f6')
BRAND_GREEN = colors.HexColor('#10b981')
BRAND_AMBER = colors.HexColor('#f59e0b')
BRAND_ROSE  = colors.HexColor('#f43f5e')
BRAND_VIOLET = colors.HexColor('#8b5cf6')
WHITE = colors.white

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm

ACTION_COLORS = {
    'create': BRAND_GREEN, 'update': BRAND_BLUE, 'delete': BRAND_ROSE,
    'login': BRAND_VIOLET, 'logout': BRAND_AMBER,
}
ACTION_HEX = {
    'create': '#10b981', 'update': '#2563eb', 'delete': '#f43f5e',
    'login': '#8b5cf6', 'logout': '#f59e0b',
}


def _styles():
    getSampleStyleSheet()  # ensures reportlab's style registry is initialised
    styles = {}
    styles['title'] = ParagraphStyle('title', fontSize=16, fontName='Helvetica-Bold',
                                      textColor=BRAND_DARK, spaceAfter=2, alignment=TA_LEFT)
    styles['subtitle'] = ParagraphStyle('subtitle', fontSize=9, fontName='Helvetica',
                                         textColor=BRAND_GRAY, spaceAfter=2, alignment=TA_LEFT)
    styles['label'] = ParagraphStyle('label', fontSize=7, fontName='Helvetica-Bold',
                                      textColor=BRAND_GRAY, spaceAfter=1)
    styles['value'] = ParagraphStyle('value', fontSize=9, fontName='Helvetica-Bold',
                                      textColor=BRAND_DARK, leading=11)
    styles['mono'] = ParagraphStyle('mono', fontSize=8, fontName='Courier',
                                     textColor=BRAND_DARK, leading=10)
    styles['footer'] = ParagraphStyle('footer', fontSize=8, fontName='Helvetica-Bold',
                                       textColor=BRAND_GRAY, alignment=TA_CENTER)
    return styles


def _header_footer(canvas, doc, meta):
    canvas.saveState()
    canvas.setFillColor(BRAND_DARK)
    canvas.rect(MARGIN, PAGE_H - 2.1*cm, PAGE_W - 2*MARGIN, 1.3*cm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont('Helvetica-Bold', 13)
    canvas.drawString(MARGIN + 0.3*cm, PAGE_H - 1.4*cm, meta['school_name'])
    canvas.setFont('Helvetica', 9)
    canvas.drawRightString(PAGE_W - MARGIN - 0.3*cm, PAGE_H - 1.4*cm, meta['doc_title'])

    canvas.setStrokeColor(BRAND_LIGHT)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 1.5*cm, PAGE_W - MARGIN, 1.5*cm)
    canvas.setFillColor(BRAND_GRAY)
    canvas.setFont('Helvetica-Bold', 8)
    canvas.drawCentredString(PAGE_W / 2, 1.1*cm, 'MathPlatform — Audit Trail (Restricted, Super Admin only)')
    canvas.setFont('Helvetica', 7)
    canvas.drawRightString(PAGE_W - MARGIN, 1.1*cm, f'Page {doc.page}')
    canvas.restoreState()


def _fmt_value(v):
    if v is None or v == '':
        return '—'
    if isinstance(v, bool):
        return 'Yes' if v else 'No'
    return str(v)


def _log_card_flowable(log, styles, compact=False) -> list:
    """Flowables for one audit-log 'card': header, metadata grid, and (if
    present) its full field-level diff — bordered top/bottom by a rule
    rather than wrapped in an outer Table, since a fixed-height wrapper
    table around a variable-length KeepTogether block causes ReportLab
    layout errors once the diff table grows past a page boundary."""
    action_color = ACTION_COLORS.get(log.action, BRAND_GRAY)
    action_hex = ACTION_HEX.get(log.action, '#6b7280')
    user_label = log.user.get_full_name() if log.user else 'Unknown / deleted user'
    user_email = log.user.email if log.user else '—'

    header_row = Table([[
        Paragraph(f'<font color="{action_hex}">{log.get_action_display().upper()}</font>'
                  f'  \u00b7  {log.model_name}' + (f' #{log.object_id}' if log.object_id else ''), styles['title']),
        Paragraph(log.timestamp.strftime('%d %b %Y, %H:%M:%S'), styles['subtitle']),
    ]], colWidths=[(PAGE_W - 2*MARGIN) * 0.68, (PAGE_W - 2*MARGIN) * 0.32])
    header_row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))

    meta_pairs = [
        ('USER', user_label), ('EMAIL', user_email),
        ('IP ADDRESS', log.ip_address or '—'), ('LOG ID', f'#{log.id}'),
    ]
    label_row = [Paragraph(l, styles['label']) for l, _ in meta_pairs]
    value_row = [Paragraph(_fmt_value(v), styles['value']) for _, v in meta_pairs]
    col_w = (PAGE_W - 2*MARGIN) / len(meta_pairs)
    meta_grid = Table([label_row, value_row], colWidths=[col_w] * len(meta_pairs))
    meta_grid.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_LIGHT), ('BACKGROUND', (0, 1), (-1, 1), WHITE),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
    ]))

    body = [header_row, Spacer(1, 0.2*cm), meta_grid]

    if log.description:
        body.append(Spacer(1, 0.15*cm))
        body.append(Paragraph(log.description, styles['mono']))

    changes = log.changes or {}
    max_fields = 6 if compact else 100
    if changes:
        body.append(Spacer(1, 0.2*cm))
        diff_rows = [[
            Paragraph('FIELD', styles['label']), Paragraph('OLD VALUE', styles['label']),
            Paragraph('NEW VALUE', styles['label']),
        ]]
        for field, change in list(changes.items())[:max_fields]:
            diff_rows.append([
                Paragraph(field, styles['mono']),
                Paragraph(f'<font color="#f43f5e">{_fmt_value(change.get("old"))}</font>', styles['mono']),
                Paragraph(f'<font color="#10b981">{_fmt_value(change.get("new"))}</font>', styles['mono']),
            ])
        remaining = len(changes) - max_fields
        if remaining > 0:
            diff_rows.append([Paragraph(f'… and {remaining} more field(s)', styles['subtitle']), '', ''])
        diff_table = Table(diff_rows, colWidths=[
            (PAGE_W - 2*MARGIN) * 0.28, (PAGE_W - 2*MARGIN) * 0.36, (PAGE_W - 2*MARGIN) * 0.36,
        ])
        diff_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_DARK), ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, BRAND_LIGHT]),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ]))
        body.append(diff_table)
    else:
        body.append(Spacer(1, 0.15*cm))
        body.append(Paragraph('No field-level changes recorded for this entry.', styles['subtitle']))

    wrapper = [
        HRFlowable(width='100%', thickness=1.4, color=action_color, spaceBefore=0, spaceAfter=6),
        KeepTogether(body),
        HRFlowable(width='100%', thickness=0.5, color=BRAND_LIGHT, spaceBefore=6, spaceAfter=0),
    ]
    return wrapper


def generate_single_card_pdf(log, extra: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2.9*cm, bottomMargin=2.0*cm,
                             leftMargin=MARGIN, rightMargin=MARGIN)
    styles = _styles()
    story = [*_log_card_flowable(log, styles, compact=False)]
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(
        f'Exported {datetime.now().strftime("%d %B %Y, %H:%M")} by {extra.get("generated_by", "—")} '
        f'· Restricted to Super Admin accounts', styles['subtitle'],
    ))
    meta = {'school_name': extra['school_name'], 'doc_title': f'Audit Log Card #{log.id}'}
    doc.build(story, onFirstPage=lambda c, d: _header_footer(c, d, meta),
              onLaterPages=lambda c, d: _header_footer(c, d, meta))
    return buf.getvalue()


def generate_batch_cards_pdf(logs: list, extra: dict) -> bytes:
    """One card per log entry, several to a page — the batch counterpart
    of generate_single_card_pdf for exporting a filtered result set."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2.9*cm, bottomMargin=2.0*cm,
                             leftMargin=MARGIN, rightMargin=MARGIN)
    styles = _styles()
    story = [Paragraph(f'{len(logs)} audit log entr{"y" if len(logs) == 1 else "ies"} exported',
                        styles['subtitle'])]
    story.append(Spacer(1, 0.3*cm))
    for i, log in enumerate(logs):
        story.extend(_log_card_flowable(log, styles, compact=True))
        story.append(Spacer(1, 0.35*cm))
        if (i + 1) % 4 == 0 and i + 1 < len(logs):
            story.append(PageBreak())

    meta = {'school_name': extra['school_name'], 'doc_title': 'Audit Log — Batch Export'}
    doc.build(story, onFirstPage=lambda c, d: _header_footer(c, d, meta),
              onLaterPages=lambda c, d: _header_footer(c, d, meta))
    return buf.getvalue()
