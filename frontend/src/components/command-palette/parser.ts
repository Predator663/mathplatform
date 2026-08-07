export interface ParsedCommand {
  command: string;
  subcommand: string | null;
  args: string[];
  flags: Record<string, string>;
  raw: string;
}

/**
 * Splits a line like:
 *   analytics send --to a@b.com,c@d.com --report at-risk --classroom "Form 2"
 * into command="analytics", subcommand="send", args=[], flags={to, report, classroom}.
 * Supports quoted strings ("...") so flag values can contain spaces.
 */
export function parseCommandLine(input: string): ParsedCommand | null {
  const raw = input.trim();
  if (!raw) return null;

  const tokens: string[] = [];
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(raw))) {
    tokens.push(m[1] ?? m[2] ?? m[3]);
  }
  if (tokens.length === 0) return null;

  const command = tokens[0].toLowerCase();
  const rest = tokens.slice(1);

  const flags: Record<string, string> = {};
  const positional: string[] = [];
  for (let i = 0; i < rest.length; i++) {
    const tok = rest[i];
    if (tok.startsWith('--')) {
      const eq = tok.indexOf('=');
      if (eq !== -1) {
        flags[tok.slice(2, eq)] = tok.slice(eq + 1);
      } else {
        const next = rest[i + 1];
        if (next !== undefined && !next.startsWith('--')) {
          flags[tok.slice(2)] = next;
          i++;
        } else {
          flags[tok.slice(2)] = 'true';
        }
      }
    } else {
      positional.push(tok);
    }
  }

  // First positional token (if it's not itself a flag value already
  // consumed above) is treated as a subcommand, e.g. `students find-duplicates`.
  const subcommand = positional[0] ?? null;
  const args = positional.slice(1);

  return { command, subcommand, args, flags, raw };
}

/** Splits a comma-separated flag value into trimmed, non-empty parts. */
export function splitList(value: string | undefined): string[] {
  if (!value) return [];
  return value.split(',').map(s => s.trim()).filter(Boolean);
}
