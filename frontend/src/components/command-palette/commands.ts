import type { NavigateFunction } from 'react-router-dom';
import type { User } from '../../types';
import { studentsApi, notificationsApi, examsApi, authApi } from '../../api';
import { useAuthStore } from '../../store/auth';
import { useThemeStore } from '../../store/theme';
import { usePaletteEffects } from './paletteEffects';
import { ROUTES, type RouteEntry } from './routes';
import { parseCommandLine, splitList, type ParsedCommand } from './parser';

export type Tone = 'default' | 'success' | 'error' | 'warn' | 'dim' | 'accent';
export interface OutputLine { text: string; tone?: Tone; }

export interface CommandContext {
  navigate: NavigateFunction;
  user: User | null;
  close: () => void;
}

export interface CommandDef {
  name: string;
  aliases?: string[];
  usage: string;
  description: string;
  adminOnly?: boolean;
  handler: (ctx: CommandContext, parsed: ParsedCommand) => Promise<OutputLine[]> | OutputLine[];
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Loose shapes for the fields these commands actually read off search
// results — the api layer returns AxiosResponse<any>, so these just give
// the .forEach/.map callbacks something concrete to type against.
interface StudentProfileLike {
  id: number; full_name: string; student_id: string; email: string;
  classroom_name: string | null; stream_name: string | null; is_active: boolean;
}
interface ExamLike { title: string; exam_type?: string; exam_date?: string; }
interface ClassroomLike { name: string; academic_year?: string; }

function isStaff(user: User | null) {
  return user?.role === 'teacher' || user?.role === 'super_admin';
}

/** Resolves a `--classroom` flag (numeric id or a name/keyword) to an id. */
async function resolveClassroomId(flagValue: string): Promise<{ id?: number; error?: string }> {
  if (/^\d+$/.test(flagValue)) return { id: Number(flagValue) };
  try {
    const res = await studentsApi.classrooms({ search: flagValue, page_size: 1 });
    const match = res.data?.results?.[0];
    if (!match) return { error: `No classroom found matching "${flagValue}".` };
    return { id: match.id };
  } catch {
    return { error: 'Failed to resolve --classroom.' };
  }
}

/** Resolves a `--student` flag (numeric id, student code, or a name) to an id. */
async function resolveStudentId(flagValue: string): Promise<{ id?: number; name?: string; error?: string }> {
  if (/^\d+$/.test(flagValue)) return { id: Number(flagValue) };
  try {
    const res = await studentsApi.students({ search: flagValue, page_size: 2 });
    const results = res.data?.results ?? [];
    if (results.length === 0) return { error: `No student found matching "${flagValue}".` };
    if (results.length > 1) return { error: `"${flagValue}" matches ${results.length} students — try their student ID instead.` };
    return { id: results[0].id, name: results[0].full_name };
  } catch {
    return { error: 'Failed to resolve --student.' };
  }
}

function downloadFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function toCSV(rows: Record<string, unknown>[]): string {
  if (rows.length === 0) return '';
  const headers = Object.keys(rows[0]);
  const escape = (v: unknown) => {
    const s = v === null || v === undefined ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.join(',')];
  rows.forEach(r => lines.push(headers.map(h => escape(r[h])).join(',')));
  return lines.join('\n');
}

function fuzzyFindRoutes(query: string, user: User | null): RouteEntry[] {
  const q = query.toLowerCase().trim();
  const isAdmin = user?.role === 'super_admin';
  const pool = ROUTES.filter(r => !r.adminOnly || isAdmin);
  if (!q) return [];

  const scored = pool.map(r => {
    const label = r.label.toLowerCase();
    const path = r.path.toLowerCase();
    let score = 0;
    if (path === `/${q}` || label === q) score = 100;
    else if (path.endsWith(q) || label.startsWith(q)) score = 80;
    else if (label.includes(q)) score = 60;
    else if (path.includes(q)) score = 50;
    else if (r.keywords.some(k => k.includes(q) || q.includes(k))) score = 40;
    return { r, score };
  }).filter(x => x.score > 0);

  scored.sort((a, b) => b.score - a.score);
  return scored.map(x => x.r);
}

export const COMMANDS: CommandDef[] = [
  {
    name: 'help',
    aliases: ['?', 'commands'],
    usage: 'help [command]',
    description: 'List every available command, or show usage for one',
    handler: (_ctx, parsed) => {
      const target = parsed.subcommand;
      if (target) {
        const cmd = COMMANDS.find(c => c.name === target || c.aliases?.includes(target));
        if (!cmd) return [{ text: `No such command: ${target}`, tone: 'error' }];
        return [
          { text: `${cmd.name}${cmd.aliases?.length ? ` (aliases: ${cmd.aliases.join(', ')})` : ''}`, tone: 'accent' },
          { text: `  usage: ${cmd.usage}`, tone: 'dim' },
          { text: `  ${cmd.description}` },
        ];
      }
      const lines: OutputLine[] = [{ text: 'AVAILABLE COMMANDS', tone: 'accent' }];
      COMMANDS.forEach(c => {
        lines.push({ text: `  ${c.usage.padEnd(46)} ${c.description}`, tone: 'default' });
      });
      lines.push({ text: '', tone: 'default' });
      lines.push({ text: 'Tip: goto accepts partial names/keywords, e.g. "goto risk"', tone: 'dim' });
      return lines;
    },
  },
  {
    name: 'whoami',
    usage: 'whoami',
    description: 'Show the current signed-in user',
    handler: (ctx) => {
      if (!ctx.user) return [{ text: 'Not signed in.', tone: 'error' }];
      return [
        { text: `${ctx.user.full_name} <${ctx.user.email}>`, tone: 'success' },
        { text: `role: ${ctx.user.role}`, tone: 'dim' },
      ];
    },
  },
  {
    name: 'goto',
    aliases: ['nav', 'cd', 'open'],
    usage: 'goto <page name or keyword>',
    description: 'Jump to any page on the site',
    handler: (ctx, parsed) => {
      const query = [parsed.subcommand, ...parsed.args].filter(Boolean).join(' ');
      if (!query) return [{ text: 'Usage: goto <page name>. Try "help goto" or "goto students".', tone: 'warn' }];
      const matches = fuzzyFindRoutes(query, ctx.user);
      if (matches.length === 0) return [{ text: `No page matches "${query}".`, tone: 'error' }];
      const best = matches[0];
      ctx.navigate(best.path);
      ctx.close();
      return [{ text: `→ ${best.label} (${best.path})`, tone: 'success' }];
    },
  },
  {
    name: 'theme',
    usage: 'theme <dark|light|toggle>',
    description: 'Switch the site theme',
    handler: (_ctx, parsed) => {
      const target = (parsed.subcommand ?? '').toLowerCase();
      const store = useThemeStore.getState();
      if (target === 'toggle' || !target) { store.toggleTheme(); return [{ text: `Theme → ${useThemeStore.getState().theme}`, tone: 'success' }]; }
      if (target === 'dark' || target === 'light') { store.setTheme(target); return [{ text: `Theme → ${target}`, tone: 'success' }]; }
      return [{ text: 'Usage: theme <dark|light|toggle>', tone: 'warn' }];
    },
  },
  {
    name: 'clear',
    aliases: ['cls'],
    usage: 'clear',
    description: 'Clear the terminal output',
    handler: () => [], // intercepted before dispatch — see CommandPalette.tsx
  },
  {
    name: 'exit',
    aliases: ['quit', 'q'],
    usage: 'exit',
    description: 'Close the command palette',
    handler: (ctx) => { ctx.close(); return [{ text: 'Closing…', tone: 'dim' }]; },
  },
  {
    name: 'logout',
    usage: 'logout confirm',
    description: 'Sign out of your account (requires confirmation)',
    handler: async (ctx, parsed) => {
      if (parsed.subcommand !== 'confirm') {
        return [{ text: 'This will sign you out. Type "logout confirm" to proceed.', tone: 'warn' }];
      }
      const { refreshToken, clearAuth } = useAuthStore.getState();
      try { if (refreshToken) await authApi.logout(refreshToken); } catch { /* ignore */ }
      clearAuth();
      ctx.navigate('/login');
      ctx.close();
      return [{ text: 'Signed out.', tone: 'success' }];
    },
  },
  {
    name: 'students',
    usage: 'students find-duplicates [--by name|email|index_number|parent_phone|date_of_birth]',
    description: 'Find duplicate student records',
    handler: async (ctx, parsed) => {
      if (parsed.subcommand !== 'find-duplicates') {
        return [{ text: 'Usage: students find-duplicates [--by <field>]', tone: 'warn' }];
      }
      const by = parsed.flags.by || 'name';
      try {
        const res = await studentsApi.duplicateStudents({ by });
        const groups: { key: string; count: number }[] = res.data?.groups ?? [];
        if (groups.length === 0) return [{ text: `No duplicates found matching by "${by}".`, tone: 'success' }];
        const lines: OutputLine[] = [{ text: `Found ${groups.length} duplicate group(s) matching by "${by}":`, tone: 'accent' }];
        groups.slice(0, 15).forEach(g => lines.push({ text: `  [${g.count}x] ${g.key || '(blank)'}` }));
        if (groups.length > 15) lines.push({ text: `  … and ${groups.length - 15} more`, tone: 'dim' });
        lines.push({ text: 'Open Students → Find Duplicates to review and clean these up.', tone: 'dim' });
        return lines;
      } catch (err) {
        const e = err as { response?: { data?: { detail?: string } } };
        return [{ text: e?.response?.data?.detail ?? 'Failed to search for duplicates.', tone: 'error' }];
      }
    },
  },
  {
    name: 'notifications',
    usage: 'notifications test | notifications failures',
    description: 'Send a test email, or inspect recent failed sends (admin only)',
    adminOnly: true,
    handler: async (ctx, parsed) => {
      if (ctx.user?.role !== 'super_admin') return [{ text: 'Only administrators can access this.', tone: 'error' }];

      if (parsed.subcommand === 'failures') {
        try {
          const res = await notificationsApi.failures();
          const { total, grouped, recent } = res.data ?? { total: 0, grouped: [], recent: [] };
          if (!total) return [{ text: 'No failed sends logged. All clear.', tone: 'success' }];

          const lines: OutputLine[] = [
            { text: `NOTIFICATION FAILURES — ${total} total`, tone: 'accent' },
            { text: '', tone: 'dim' },
            { text: 'By reason:', tone: 'accent' },
          ];
          grouped.forEach((g: { error_message: string; count: number; last_seen: string | null }) => {
            lines.push({ text: `  [${g.count}x] ${g.error_message}`, tone: 'error' });
            if (g.last_seen) lines.push({ text: `        last seen: ${new Date(g.last_seen).toLocaleString()}`, tone: 'dim' });
          });
          lines.push({ text: '', tone: 'dim' });
          lines.push({ text: 'Most recent 15:', tone: 'accent' });
          recent.forEach((n: { recipient_email: string | null; category: string; subject: string; sent_at: string }) => {
            lines.push({ text: `  ${new Date(n.sent_at).toLocaleString()}  ${n.recipient_email ?? '(no recipient)'}  [${n.category}]  ${n.subject}`, tone: 'dim' });
          });
          return lines;
        } catch (err) {
          const e = err as { response?: { data?: { detail?: string } } };
          return [{ text: e?.response?.data?.detail ?? 'Failed to fetch failure log.', tone: 'error' }];
        }
      }

      if (parsed.subcommand !== 'test') return [{ text: 'Usage: notifications test | notifications failures', tone: 'warn' }];
      try {
        const res = await notificationsApi.testEmail();
        return [{ text: res.data?.detail ?? 'Test email sent.', tone: 'success' }];
      } catch (err) {
        const e = err as { response?: { data?: { detail?: string } } };
        return [{ text: e?.response?.data?.detail ?? 'Failed to send test email.', tone: 'error' }];
      }
    },
  },
  {
    name: 'analytics',
    usage: 'analytics send --to <email[,..]> --report <overview|at-risk|class|student> [--classroom <name>] [--student <name>]',
    description: 'Email an analytics report to any address(es), including a single student\'s report',
    adminOnly: true,
    handler: async (ctx, parsed) => {
      if (parsed.subcommand !== 'send') {
        return [{ text: 'Usage: analytics send --to a@b.com,c@d.com --report overview', tone: 'warn' }];
      }
      if (!isStaff(ctx.user)) return [{ text: 'Only teachers and administrators can send analytics reports.', tone: 'error' }];

      const recipients = splitList(parsed.flags.to ?? parsed.flags.email ?? parsed.flags.emails);
      if (recipients.length === 0) {
        return [{ text: 'Missing --to. Example: analytics send --to a@b.com,c@d.com --report overview', tone: 'error' }];
      }
      const invalid = recipients.filter(r => !EMAIL_RE.test(r));
      if (invalid.length > 0) {
        return [{ text: `Invalid email address(es): ${invalid.join(', ')}`, tone: 'error' }];
      }

      const reportType = (parsed.flags.report || 'overview').toLowerCase();
      if (!['overview', 'at-risk', 'class', 'student'].includes(reportType)) {
        return [{ text: 'Unknown --report type. Choose one of: overview, at-risk, class, student.', tone: 'error' }];
      }

      let classroomId: number | undefined;
      if (parsed.flags.classroom) {
        const resolved = await resolveClassroomId(parsed.flags.classroom);
        if (resolved.error) return [{ text: resolved.error, tone: 'error' }];
        classroomId = resolved.id;
      }
      if (reportType === 'class' && !classroomId) {
        return [{ text: 'A "class" report needs --classroom <name or id>.', tone: 'error' }];
      }

      let studentId: number | undefined;
      const studentFlag = parsed.flags.student;
      if (reportType === 'student') {
        if (!studentFlag) return [{ text: 'A "student" report needs --student <name or id>.', tone: 'error' }];
        const resolved = await resolveStudentId(studentFlag);
        if (resolved.error) return [{ text: resolved.error, tone: 'error' }];
        studentId = resolved.id;
      }

      try {
        const res = await notificationsApi.sendAnalyticsReport({
          recipients, report_type: reportType, classroom_id: classroomId, student_id: studentId,
        });
        const data = res.data as { recipient_count?: number; report_title?: string };
        return [
          { text: `✓ "${data.report_title}" sent to ${data.recipient_count} recipient(s):`, tone: 'success' },
          { text: `  ${recipients.join(', ')}`, tone: 'dim' },
        ];
      } catch (err) {
        const e = err as { response?: { data?: { detail?: string } } };
        return [{ text: e?.response?.data?.detail ?? 'Failed to send analytics report.', tone: 'error' }];
      }
    },
  },
  {
    name: 'whois',
    usage: 'whois <name or student id>',
    description: 'Look up a student and their recent performance',
    handler: async (_ctx, parsed) => {
      const query = [parsed.subcommand, ...parsed.args].filter(Boolean).join(' ');
      if (!query) return [{ text: 'Usage: whois <name or student id>', tone: 'warn' }];
      try {
        const res = await studentsApi.students({ search: query, page_size: 5 });
        const results = res.data?.results ?? [];
        if (results.length === 0) return [{ text: `No student matches "${query}".`, tone: 'error' }];
        if (results.length > 1) {
          const lines: OutputLine[] = [{ text: `${results.length} matches for "${query}":`, tone: 'accent' }];
          results.forEach((s: StudentProfileLike) => lines.push({ text: `  ${s.full_name}  [${s.student_id}]  ${s.classroom_name ?? 'No class'}` }));
          lines.push({ text: 'Narrow it down with a student ID for full detail.', tone: 'dim' });
          return lines;
        }
        const s: StudentProfileLike = results[0];
        const lines: OutputLine[] = [
          { text: `${s.full_name}  [${s.student_id}]`, tone: 'accent' },
          { text: `  class: ${s.classroom_name ?? '—'}${s.stream_name ? ` (${s.stream_name})` : ''}` },
          { text: `  email: ${s.email || '—'}` },
          { text: `  status: ${s.is_active ? 'active' : 'inactive'}`, tone: s.is_active ? 'success' : 'warn' },
        ];
        try {
          const perf = await studentsApi.studentPerformance(s.id);
          const p = perf.data as { total_exams?: number; average_percentage?: number | null; pass_rate?: number; trend?: string; predicted_necta_grade?: string | null };
          if (p.total_exams) {
            lines.push({ text: `  exams: ${p.total_exams}  avg: ${p.average_percentage}%  pass rate: ${p.pass_rate}%  trend: ${(p.trend || '').replace('_', ' ')}`, tone: 'dim' });
            if (p.predicted_necta_grade) lines.push({ text: `  predicted NECTA grade: ${p.predicted_necta_grade}`, tone: 'dim' });
          } else {
            lines.push({ text: '  no exam records yet', tone: 'dim' });
          }
        } catch { /* performance summary is a nice-to-have, not fatal */ }
        lines.push({ text: '  → goto students to view the full profile', tone: 'dim' });
        return lines;
      } catch {
        return [{ text: 'Lookup failed.', tone: 'error' }];
      }
    },
  },
  {
    name: 'grep',
    usage: 'grep <term>',
    description: 'Search students, exams, and classrooms at once',
    handler: async (_ctx, parsed) => {
      const term = [parsed.subcommand, ...parsed.args].filter(Boolean).join(' ');
      if (!term) return [{ text: 'Usage: grep <term>', tone: 'warn' }];
      try {
        const [studentsRes, examsRes, classroomsRes] = await Promise.all([
          studentsApi.students({ search: term, page_size: 5 }),
          examsApi.exams({ search: term, page_size: 5 }),
          studentsApi.classrooms({ search: term, page_size: 5 }),
        ]);
        const students: StudentProfileLike[] = studentsRes.data?.results ?? [];
        const exams: ExamLike[] = examsRes.data?.results ?? [];
        const classrooms: ClassroomLike[] = classroomsRes.data?.results ?? [];
        const total = students.length + exams.length + classrooms.length;
        const lines: OutputLine[] = [{ text: `grep "${term}" — ${total} match(es) shown`, tone: 'accent' }];
        if (students.length) {
          lines.push({ text: `STUDENTS (${studentsRes.data?.count ?? students.length})`, tone: 'accent' });
          students.forEach(s => lines.push({ text: `  ${s.full_name}  [${s.student_id}]  ${s.classroom_name ?? ''}` }));
        }
        if (exams.length) {
          lines.push({ text: `EXAMS (${examsRes.data?.count ?? exams.length})`, tone: 'accent' });
          exams.forEach(e => lines.push({ text: `  ${e.title}  ${e.exam_type ?? ''}  ${e.exam_date ?? ''}` }));
        }
        if (classrooms.length) {
          lines.push({ text: `CLASSROOMS (${classroomsRes.data?.count ?? classrooms.length})`, tone: 'accent' });
          classrooms.forEach(c => lines.push({ text: `  ${c.name}  (${c.academic_year ?? ''})` }));
        }
        if (total === 0) lines.push({ text: 'No matches anywhere.', tone: 'dim' });
        return lines;
      } catch {
        return [{ text: 'Search failed.', tone: 'error' }];
      }
    },
  },
  {
    name: 'system',
    usage: 'system status',
    description: 'Health check: database, SMTP config, failed sends (admin only)',
    adminOnly: true,
    handler: async (ctx, parsed) => {
      if (parsed.subcommand !== 'status') return [{ text: 'Usage: system status', tone: 'warn' }];
      if (ctx.user?.role !== 'super_admin') return [{ text: 'Administrators only.', tone: 'error' }];
      try {
        const res = await notificationsApi.systemStatus();
        const checks: { name: string; ok: boolean; detail: string }[] = res.data?.checks ?? [];
        const lines: OutputLine[] = [{ text: 'SYSTEM STATUS', tone: 'accent' }];
        checks.forEach(c => lines.push({ text: `  ${c.ok ? '✓' : '✗'} ${c.name.padEnd(24)} ${c.detail}`, tone: c.ok ? 'success' : 'error' }));
        return lines;
      } catch (err) {
        const e = err as { response?: { data?: { detail?: string } } };
        return [{ text: e?.response?.data?.detail ?? 'Status check failed.', tone: 'error' }];
      }
    },
  },
  {
    name: 'ping',
    usage: 'ping',
    description: 'Measure round-trip time to the API',
    handler: async () => {
      const start = performance.now();
      try {
        await notificationsApi.ping();
        const ms = Math.round(performance.now() - start);
        const tone: Tone = ms < 200 ? 'success' : ms < 600 ? 'warn' : 'error';
        return [{ text: `PONG  ${ms}ms`, tone }];
      } catch {
        const ms = Math.round(performance.now() - start);
        return [{ text: `Request failed after ${ms}ms — server unreachable.`, tone: 'error' }];
      }
    },
  },
  {
    name: 'export',
    usage: 'export students [--format csv|json] [--classroom <name>] [--active]',
    description: 'Download the (optionally filtered) student list',
    handler: async (_ctx, parsed) => {
      if (parsed.subcommand !== 'students') return [{ text: 'Usage: export students [--format csv|json]', tone: 'warn' }];
      const format = (parsed.flags.format || 'csv').toLowerCase();
      if (!['csv', 'json'].includes(format)) return [{ text: 'Unknown --format. Choose csv or json.', tone: 'error' }];

      let classroomId: number | undefined;
      if (parsed.flags.classroom) {
        const resolved = await resolveClassroomId(parsed.flags.classroom);
        if (resolved.error) return [{ text: resolved.error, tone: 'error' }];
        classroomId = resolved.id;
      }

      try {
        const res = await studentsApi.students({
          page_size: 1000,
          classroom: classroomId,
          is_active: parsed.flags.active !== undefined ? true : undefined,
        });
        const students: StudentProfileLike[] = res.data?.results ?? [];
        if (students.length === 0) return [{ text: 'No students matched — nothing to export.', tone: 'warn' }];

        const rows = students.map(s => ({
          student_id: s.student_id, name: s.full_name, email: s.email,
          classroom: s.classroom_name ?? '', stream: s.stream_name ?? '',
          status: s.is_active ? 'active' : 'inactive',
        }));

        const stamp = new Date().toISOString().slice(0, 10);
        if (format === 'json') {
          downloadFile(`students_${stamp}.json`, JSON.stringify(rows, null, 2), 'application/json');
        } else {
          downloadFile(`students_${stamp}.csv`, toCSV(rows), 'text/csv');
        }
        return [{ text: `✓ Exported ${rows.length} student(s) as ${format.toUpperCase()}.`, tone: 'success' }];
      } catch {
        return [{ text: 'Export failed.', tone: 'error' }];
      }
    },
  },
  {
    name: 'matrix',
    usage: 'matrix <on|off|toggle>',
    description: 'Toggle the digital rain background effect',
    handler: (_ctx, parsed) => {
      const target = (parsed.subcommand ?? 'toggle').toLowerCase();
      const store = usePaletteEffects.getState();
      if (target === 'on') store.setMatrix(true);
      else if (target === 'off') store.setMatrix(false);
      else store.toggleMatrix();
      return [{ text: `Matrix rain → ${usePaletteEffects.getState().matrixOn ? 'ON' : 'OFF'}`, tone: 'success' }];
    },
  },
  {
    name: 'glitch',
    usage: 'glitch',
    description: 'Replay the terminal glitch effect',
    handler: () => {
      usePaletteEffects.getState().triggerGlitch();
      return [{ text: 'signal noise injected.', tone: 'dim' }];
    },
  },
];

export function findCommand(name: string): CommandDef | undefined {
  return COMMANDS.find(c => c.name === name || c.aliases?.includes(name));
}

export { parseCommandLine };
