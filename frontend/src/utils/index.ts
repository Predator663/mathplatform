import { clsx, type ClassValue } from 'clsx';
import type { ExamType, TermType, EducationLevel } from '../types';

export function cn(...inputs: ClassValue[]) { return clsx(inputs); }

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-TZ', {
    year: 'numeric', month: 'short', day: 'numeric',
  });
}

export function formatPercent(value: number | null | undefined, decimals = 1): string {
  if (value == null) return '—';
  return `${value.toFixed(decimals)}%`;
}

export function gradeColor(pct: number): string {
  if (pct >= 75) return 'text-emerald-400';
  if (pct >= 65) return 'text-azure-400';
  if (pct >= 45) return 'text-amber-400';
  return 'text-rose-400';
}

export function gradeBg(pct: number): string {
  if (pct >= 75) return 'bg-emerald-500/15 text-emerald-400';
  if (pct >= 65) return 'bg-azure-500/15 text-azure-400';
  if (pct >= 45) return 'bg-amber-500/15 text-amber-400';
  return 'bg-rose-500/15 text-rose-400';
}

/** Letter grade from percentage */
export function tanzaniaGrade(pct: number): string {
  if (pct >= 75) return 'A';
  if (pct >= 65) return 'B';
  if (pct >= 45) return 'C';
  if (pct >= 30) return 'D';
  return 'F';
}

export function trendColor(trend: string): string {
  if (trend === 'improving') return 'text-emerald-400';
  if (trend === 'declining') return 'text-rose-400';
  return 'text-secondary';
}

export function trendIcon(trend: string): string {
  if (trend === 'improving') return '↑';
  if (trend === 'declining') return '↓';
  return '→';
}

export const EXAM_TYPE_LABELS: Record<ExamType, string> = {
  monthly_test: 'Monthly Test',
  mid_term:     'Mid-Term Exam',
  terminal:     'Terminal Exam',
  mock:         'Mock Exam (Mazoezi)',
  necta:        'NECTA',
  psle:         'PSLE (Std 7)',
  csee:         'CSEE (Form 4)',
  acsee:        'ACSEE (Form 6)',
  diagnostic:   'Diagnostic Test',
};

export const TERM_LABELS: Record<TermType, string> = {
  term_1: 'Term I (Jan–Apr)',
  term_2: 'Term II (May–Aug)',
  term_3: 'Term III (Sep–Dec)',
  annual: 'Annual',
};

export const EDUCATION_LEVEL_LABELS: Record<EducationLevel, string> = {
  pre_primary: 'Pre-Primary (Awali)',
  primary:     'Primary (Msingi)',
  o_level:     'O-Level (Form 1–4)',
  a_level:     'A-Level (Form 5–6)',
  technical:   'Technical / VETA',
};

export const EXAM_TYPE_COLORS: Record<ExamType, string> = {
  monthly_test: 'badge-violet',
  mid_term:     'badge-blue',
  terminal:     'badge-amber',
  mock:         'badge-amber',
  necta:        'badge-rose',
  psle:         'badge-rose',
  csee:         'badge-rose',
  acsee:        'badge-rose',
  diagnostic:   'badge-green',
};

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}
