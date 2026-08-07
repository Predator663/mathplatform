import type { NavigateFunction } from 'react-router-dom';
import type { User } from '../../types';
import { studentsApi, notificationsApi, authApi } from '../../api';
import { useAuthStore } from '../../store/auth';
import { useThemeStore } from '../../store/theme';
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

function isStaff(user: User | null) {
  return user?.role === 'teacher' || user?.role === 'super_admin';
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
    usage: 'notifications test',
    description: 'Send a test email to confirm SMTP delivery (admin only)',
    adminOnly: true,
    handler: async (ctx, parsed) => {
      if (ctx.user?.role !== 'super_admin') return [{ text: 'Only administrators can send a test email.', tone: 'error' }];
      if (parsed.subcommand !== 'test') return [{ text: 'Usage: notifications test', tone: 'warn' }];
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
    usage: 'analytics send --to <email[,email...]> --report <overview|at-risk|class> [--classroom <name>]',
    description: 'Email an analytics report to any address(es)',
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
      if (!['overview', 'at-risk', 'class'].includes(reportType)) {
        return [{ text: 'Unknown --report type. Choose one of: overview, at-risk, class.', tone: 'error' }];
      }

      let classroomId: number | undefined;
      const classroomFlag = parsed.flags.classroom;
      if (classroomFlag) {
        if (/^\d+$/.test(classroomFlag)) {
          classroomId = Number(classroomFlag);
        } else {
          try {
            const res = await studentsApi.classrooms({ search: classroomFlag, page_size: 1 });
            const match = res.data?.results?.[0];
            if (!match) return [{ text: `No classroom found matching "${classroomFlag}".`, tone: 'error' }];
            classroomId = match.id;
          } catch {
            return [{ text: 'Failed to resolve --classroom.', tone: 'error' }];
          }
        }
      }
      if (reportType === 'class' && !classroomId) {
        return [{ text: 'A "class" report needs --classroom <name or id>.', tone: 'error' }];
      }

      try {
        const res = await notificationsApi.sendAnalyticsReport({
          recipients, report_type: reportType, classroom_id: classroomId,
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
];

export function findCommand(name: string): CommandDef | undefined {
  return COMMANDS.find(c => c.name === name || c.aliases?.includes(name));
}

export { parseCommandLine };
