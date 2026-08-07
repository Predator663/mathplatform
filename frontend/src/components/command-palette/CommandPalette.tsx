import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/auth';
import { COMMANDS, findCommand, parseCommandLine, type OutputLine, type Tone } from './commands';

interface HistoryEntry {
  kind: 'input' | 'output';
  text: string;
  tone?: Tone;
}

const BANNER = [
  ' __  __       _   _     ____  _       _    __                       ',
  '|  \\/  | __ _| |_| |__ |  _ \\| | __ _| |_ / _| ___  _ __ _ __ ___   ',
  '| |\\/| |/ _\` | __| \'_ \\| |_) | |/ _\` | __| |_ / _ \\| \'__| \'_ \` _ \\  ',
  '| |  | | (_| | |_| | | |  __/| | (_| | |_|  _| (_) | |  | | | | | | ',
  '|_|  |_|\\__,_|\\__|_| |_|_|   |_|\\__,_|\\__|_|  \\___/|_|  |_| |_| |_| ',
];

function toneClass(tone?: Tone) {
  switch (tone) {
    case 'success': return 'text-[#4dff4d]';
    case 'error': return 'text-[#ff4d4d]';
    case 'warn': return 'text-[#ffd24d]';
    case 'accent': return 'text-[#4dffe0] font-semibold';
    case 'dim': return 'text-[#2f8f4e]';
    default: return 'text-[#39ff6a]';
  }
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [cmdHistory, setCmdHistory] = useState<string[]>([]);
  const [histIndex, setHistIndex] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const close = useCallback(() => setOpen(false), []);

  // Global combinational shortcut: Ctrl/Cmd + Shift + K, from anywhere,
  // even while focus is inside another input.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const combo = (e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'k';
      if (combo) {
        e.preventDefault();
        setOpen((prev) => !prev);
        return;
      }
      if (e.key === 'Escape' && open) {
        e.preventDefault();
        setOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open]);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 30);
      if (history.length === 0) {
        setHistory([
          ...BANNER.map((line): HistoryEntry => ({ kind: 'output', text: line, tone: 'accent' })),
          { kind: 'output', text: '', tone: 'default' },
          { kind: 'output', text: `root@${(user?.role ?? 'guest')}:~$ session initiated. type "help" to list commands.`, tone: 'dim' },
          { kind: 'output', text: '', tone: 'default' },
        ]);
      }
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [history, busy]);

  const push = (lines: HistoryEntry[]) => setHistory((prev) => [...prev, ...lines]);

  const run = async (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed) return;
    push([{ kind: 'input', text: trimmed }]);
    setCmdHistory((prev) => [...prev, trimmed]);
    setHistIndex(null);

    const parsed = parseCommandLine(trimmed);
    if (!parsed) return;

    if (parsed.command === 'clear' || parsed.command === 'cls') {
      setHistory([]);
      return;
    }

    const cmd = findCommand(parsed.command);
    if (!cmd) {
      push([{ kind: 'output', text: `command not found: ${parsed.command} — type "help" for a list.`, tone: 'error' }]);
      return;
    }

    setBusy(true);
    try {
      const result = await cmd.handler({ navigate, user, close }, parsed);
      const lines: OutputLine[] = Array.isArray(result) ? result : [];
      push(lines.map((l): HistoryEntry => ({ kind: 'output', text: l.text, tone: l.tone })));
    } catch {
      push([{ kind: 'output', text: 'Unexpected error running that command.', tone: 'error' }]);
    } finally {
      setBusy(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      const val = input;
      setInput('');
      void run(val);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (cmdHistory.length === 0) return;
      const nextIndex = histIndex === null ? cmdHistory.length - 1 : Math.max(0, histIndex - 1);
      setHistIndex(nextIndex);
      setInput(cmdHistory[nextIndex]);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (histIndex === null) return;
      const nextIndex = histIndex + 1;
      if (nextIndex >= cmdHistory.length) { setHistIndex(null); setInput(''); }
      else { setHistIndex(nextIndex); setInput(cmdHistory[nextIndex]); }
    } else if (e.key === 'Tab') {
      e.preventDefault();
      const firstToken = input.split(' ')[0]?.toLowerCase() ?? '';
      if (!firstToken) return;
      const match = COMMANDS.find(c => c.name.startsWith(firstToken) || c.aliases?.some(a => a.startsWith(firstToken)));
      if (match) setInput(match.name + ' ');
    }
  };

  if (!open) return null;

  const firstToken = input.split(' ')[0]?.toLowerCase() ?? '';
  const showSuggestions = firstToken.length > 0 && !input.includes(' ');
  const suggestions = showSuggestions
    ? COMMANDS.filter(c => c.name.startsWith(firstToken) || c.aliases?.some(a => a.startsWith(firstToken))).slice(0, 6)
    : [];

  return (
    <div
      className="fixed inset-0 z-[999] flex items-start justify-center pt-[8vh] px-4"
      style={{ background: 'rgba(0,0,0,0.82)' }}
      onClick={close}
    >
      <div
        className="w-full max-w-3xl rounded-lg overflow-hidden border relative"
        style={{
          background: '#020603',
          borderColor: 'rgba(57,255,106,0.35)',
          boxShadow: '0 0 0 1px rgba(57,255,106,0.08), 0 0 40px rgba(57,255,106,0.15), 0 20px 60px rgba(0,0,0,0.6)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Scanline overlay */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage: 'repeating-linear-gradient(0deg, #39ff6a 0px, #39ff6a 1px, transparent 1px, transparent 3px)',
          }}
        />

        {/* Title bar */}
        <div className="flex items-center justify-between px-4 py-2 border-b" style={{ borderColor: 'rgba(57,255,106,0.2)', background: 'rgba(57,255,106,0.04)' }}>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#ff5f56' }} />
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#ffbd2e' }} />
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#27c93f' }} />
            <span className="ml-3 text-[11px] font-mono tracking-widest text-[#39ff6a]/70 uppercase">fsociety-shell — mathplatform</span>
          </div>
          <kbd className="text-[10px] font-mono text-[#39ff6a]/50 border border-[#39ff6a]/20 rounded px-1.5 py-0.5">esc</kbd>
        </div>

        {/* Output */}
        <div
          ref={scrollRef}
          className="font-mono text-[13px] leading-[1.5] px-4 py-3 overflow-y-auto no-scrollbar"
          style={{ maxHeight: '48vh', textShadow: '0 0 6px rgba(57,255,106,0.35)' }}
        >
          {history.map((line, i) => (
            <div key={i} className={line.kind === 'input' ? 'text-[#39ff6a]' : toneClass(line.tone)}>
              {line.kind === 'input' ? <><span className="text-[#2f8f4e]">{'>'}</span> {line.text}</> : (line.text || '\u00A0')}
            </div>
          ))}
          {busy && <div className="text-[#2f8f4e]">…</div>}
        </div>

        {/* Input line */}
        <div className="flex items-center gap-2 px-4 py-3 border-t" style={{ borderColor: 'rgba(57,255,106,0.2)' }}>
          <span className="font-mono text-[#39ff6a]">{'>'}</span>
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="type a command… (help)"
            spellCheck={false}
            autoComplete="off"
            className="flex-1 bg-transparent outline-none font-mono text-[13px] text-[#39ff6a] placeholder:text-[#2f8f4e]/60 caret-[#39ff6a]"
            style={{ textShadow: '0 0 6px rgba(57,255,106,0.35)' }}
          />
          <span className="w-2 h-4 bg-[#39ff6a] animate-pulse" style={{ boxShadow: '0 0 6px rgba(57,255,106,0.6)' }} />
        </div>

        {/* Suggestions */}
        {suggestions.length > 0 && (
          <div className="flex flex-wrap gap-1.5 px-4 pb-3 -mt-1">
            {suggestions.map((c) => (
              <button
                key={c.name}
                className="text-[10px] font-mono px-2 py-0.5 rounded border border-[#39ff6a]/25 text-[#39ff6a]/80 hover:bg-[#39ff6a]/10 transition-colors"
                onClick={() => { setInput(c.name + ' '); inputRef.current?.focus(); }}
              >
                {c.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
