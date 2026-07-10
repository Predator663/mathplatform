import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, Search, X } from 'lucide-react';
import { cn } from '../../utils';

export interface SearchableSelectOption {
  value: string | number;
  label: string;
  /** Optional secondary text searched too but shown muted (e.g. a student ID). */
  sublabel?: string;
}

interface SearchableSelectProps {
  label?: string;
  error?: string;
  placeholder?: string;
  /** Shown in the input when the dropdown is open and nothing is typed yet. */
  searchPlaceholder?: string;
  options: SearchableSelectOption[];
  value: string | number;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
  emptyMessage?: string;
}

/**
 * A searchable dropdown. Behaves like a native <select> (single value,
 * onChange(value)) but renders a filterable text input + list instead of
 * the OS-native picker, so long lists (e.g. every student in a class) can
 * be narrowed by typing instead of scrolling.
 */
export function SearchableSelect({
  label, error, placeholder = 'Select…', searchPlaceholder = 'Type to search…',
  options, value, onChange, disabled, className, emptyMessage = 'No matches found',
}: SearchableSelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlighted, setHighlighted] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const selected = useMemo(
    () => options.find(o => String(o.value) === String(value)),
    [options, value]
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter(o =>
      o.label.toLowerCase().includes(q) ||
      (o.sublabel ? o.sublabel.toLowerCase().includes(q) : false)
    );
  }, [options, query]);

  // Close on outside click.
  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery('');
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  useEffect(() => {
    if (open) {
      setHighlighted(0);
      // Focus the search input as soon as the list opens.
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    setHighlighted(0);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    const el = listRef.current?.children[highlighted] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  }, [highlighted, open]);

  function commit(opt: SearchableSelectOption) {
    onChange(String(opt.value));
    setOpen(false);
    setQuery('');
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        e.preventDefault();
        setOpen(true);
      }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlighted(h => Math.min(h + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlighted(h => Math.max(h - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[highlighted]) commit(filtered[highlighted]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setOpen(false);
      setQuery('');
    }
  }

  const selectId = label?.toLowerCase().replace(/\s+/g, '-');

  return (
    <div className="flex flex-col gap-1.5" ref={rootRef}>
      {label && <label htmlFor={selectId} className="label">{label}</label>}
      <div className="relative">
        <div
          className={cn(
            'input flex items-center gap-2 cursor-text',
            error && 'border-rose-500/60',
            disabled && 'opacity-50 cursor-not-allowed',
            className
          )}
          tabIndex={open || disabled ? -1 : 0}
          role={open ? undefined : 'combobox'}
          aria-expanded={open}
          onClick={() => !disabled && setOpen(true)}
          onKeyDown={open ? undefined : onKeyDown}
        >
          <Search size={14} className="shrink-0" style={{ color: 'var(--text-muted)' }} />
          {open ? (
            <input
              id={selectId}
              ref={inputRef}
              className="flex-1 bg-transparent outline-none min-w-0"
              disabled={disabled}
              placeholder={searchPlaceholder}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
            />
          ) : (
            <span
              id={selectId}
              className="flex-1 truncate text-sm"
              style={{ color: selected ? 'var(--text-primary)' : 'var(--text-muted)' }}
            >
              {selected ? selected.label : placeholder}
            </span>
          )}
          {selected && !disabled && (
            <button
              type="button"
              tabIndex={-1}
              className="shrink-0 rounded-md p-0.5 hover:bg-black/10"
              onClick={e => { e.stopPropagation(); onChange(''); setQuery(''); }}
              aria-label="Clear selection"
            >
              <X size={13} style={{ color: 'var(--text-muted)' }} />
            </button>
          )}
          <ChevronDown
            size={14}
            className={cn('shrink-0 transition-transform', open && 'rotate-180')}
            style={{ color: 'var(--text-muted)' }}
          />
        </div>

        {open && !disabled && (
          <ul
            ref={listRef}
            role="listbox"
            className="absolute z-50 mt-1.5 w-full max-h-64 overflow-y-auto rounded-xl border shadow-lg py-1"
            style={{ backgroundColor: 'var(--bg-900)', borderColor: 'var(--border)' }}
          >
            {filtered.length === 0 && (
              <li className="px-3.5 py-2.5 text-sm" style={{ color: 'var(--text-muted)' }}>
                {emptyMessage}
              </li>
            )}
            {filtered.map((opt, i) => (
              <li
                key={opt.value}
                role="option"
                aria-selected={String(opt.value) === String(value)}
                className={cn(
                  'px-3.5 py-2 text-sm cursor-pointer flex items-center justify-between gap-2',
                  i === highlighted && 'bg-azure-500/15',
                  String(opt.value) === String(value) && 'font-semibold'
                )}
                style={{ color: 'var(--text-primary)' }}
                onMouseEnter={() => setHighlighted(i)}
                onMouseDown={e => e.preventDefault()} // keep focus, avoid input blur before click
                onClick={() => commit(opt)}
              >
                <span className="truncate">{opt.label}</span>
                {opt.sublabel && (
                  <span className="text-xs shrink-0" style={{ color: 'var(--text-muted)' }}>
                    {opt.sublabel}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      {error && <p className="text-xs text-rose-400 mt-0.5">{error}</p>}
    </div>
  );
}
