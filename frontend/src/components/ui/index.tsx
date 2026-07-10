import React from 'react';
import type { ReactNode, ButtonHTMLAttributes } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../utils';
export { Pagination } from './Pagination';
export { default as ThemeToggle } from './ThemeToggle';
export { SearchableSelect } from './SearchableSelect';
export type { SearchableSelectOption } from './SearchableSelect';

// ── Spinner ───────────────────────────────────────────────────────────────────
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn('animate-spin', className)} />;
}

export function LoadingPage() {
  return (
    <div className="flex items-center justify-center h-40 md:h-64">
      <Spinner className="w-7 h-7 text-azure-500" />
    </div>
  );
}

// ── Button ────────────────────────────────────────────────────────────────────
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  children: ReactNode;
}

export function Button({ variant = 'primary', size = 'md', loading, children, className, disabled, ...props }: ButtonProps) {
  const base = 'inline-flex items-center gap-1.5 font-display font-semibold rounded-xl transition-all duration-150 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed select-none active:scale-[0.98]';
  const variants = {
    primary: 'bg-azure-500 hover:bg-azure-600 text-white focus:ring-2 focus:ring-azure-500/40',
    secondary: 'bg-surface-700 hover:bg-surface-600 border border-surface text-primary focus:ring-2 focus:ring-azure-500/30',
    danger: 'bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-400',
    ghost: 'hover:bg-surface-700 text-secondary hover:text-primary',
  };
  const sizes = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2.5 text-sm',
    lg: 'px-5 py-3 text-sm md:text-base',
  };
  return (
    <button className={cn(base, variants[variant], sizes[size], className)} disabled={disabled || loading} {...props}>
      {loading && <Spinner className="w-3.5 h-3.5" />}
      {children}
    </button>
  );
}

// ── Input ─────────────────────────────────────────────────────────────────────
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string; error?: string;
}
export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className, id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');
    return (
      <div className="flex flex-col gap-1.5">
        {label && <label htmlFor={inputId} className="label">{label}</label>}
        <input
          id={inputId} ref={ref}
          className={cn('input', error && 'border-rose-500/60 focus:ring-rose-500/40', className)}
          {...props}
        />
        {error && <p className="text-xs text-rose-400 mt-0.5">{error}</p>}
      </div>
    );
  }
);
Input.displayName = 'Input';

// ── Select ────────────────────────────────────────────────────────────────────
interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string; error?: string;
  options: { value: string | number; label: string }[];
}
export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, options, className, id, ...props }, ref) => {
    const selectId = id || label?.toLowerCase().replace(/\s+/g, '-');
    return (
      <div className="flex flex-col gap-1.5">
        {label && <label htmlFor={selectId} className="label">{label}</label>}
        <select id={selectId} ref={ref} className={cn('input', error && 'border-rose-500/60', className)} {...props}>
          {options.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
        </select>
        {error && <p className="text-xs text-rose-400 mt-0.5">{error}</p>}
      </div>
    );
  }
);
Select.displayName = 'Select';

// ── Modal ─────────────────────────────────────────────────────────────────────
interface ModalProps {
  open: boolean; onClose: () => void; title: string;
  children: ReactNode; footer?: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}
export function Modal({ open, onClose, title, children, footer, size = 'md' }: ModalProps) {
  if (!open) return null;
  const widths = { sm: 'max-w-sm', md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl' };
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div
        className={cn(
          'relative w-full card shadow-2xl',
          'rounded-t-2xl sm:rounded-2xl',
          'max-h-[92vh] overflow-y-auto',
          widths[size]
        )}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b sticky top-0 z-10 rounded-t-2xl" style={{backgroundColor: "var(--bg-800)", borderColor: "var(--border)"}}>
          <h3 className="section-title">{title}</h3>
          <button onClick={onClose} className="text-secondary hover:text-primary transition-colors w-8 h-8 flex items-center justify-center rounded-lg hover:bg-surface-700">✕</button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="px-5 py-4 border-t flex justify-end gap-3 sticky bottom-0" style={{backgroundColor: "var(--bg-800)", borderColor: "var(--border)"}}>{footer}</div>}
      </div>
    </div>
  );
}

// ── Table ─────────────────────────────────────────────────────────────────────
export function Table({ headers, children, className }: { headers: string[]; children: ReactNode; className?: string }) {
  return (
    <div className={cn('overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0', className)}>
      <table className="w-full text-sm min-w-max md:min-w-0">
        <thead>
          <tr className="border-b border-surface">
            {headers.map(h => (
              <th key={h} className="text-left text-xs font-display font-semibold text-secondary uppercase tracking-widest py-3 px-3 whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function Tr({ children, className, onClick }: { children: ReactNode; className?: string; onClick?: () => void }) {
  return (
    <tr className={cn('border-b border-surface hover:bg-surface-700/30 transition-colors', onClick && 'cursor-pointer', className)} onClick={onClick}>
      {children}
    </tr>
  );
}

export function Td({ children, className }: { children: ReactNode; className?: string }) {
  return <td className={cn('py-3 px-3 text-primary/80', className)}>{children}</td>;
}

// ── Empty State ───────────────────────────────────────────────────────────────
export function EmptyState({ icon, title, message }: { icon?: ReactNode; title: string; message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 md:py-16 gap-3 text-center px-4">
      {icon && <div className="text-secondary mb-2">{icon}</div>}
      <p className="font-display font-semibold text-primary">{title}</p>
      {message && <p className="text-muted max-w-xs">{message}</p>}
    </div>
  );
}

// ── Stat Card ─────────────────────────────────────────────────────────────────
interface StatCardProps {
  label: string; value: string | number; sub?: string;
  color?: 'blue' | 'green' | 'amber' | 'rose' | 'violet';
  icon?: ReactNode;
}
export function StatCard({ label, value, sub, color = 'blue', icon }: StatCardProps) {
  const colors = {
    blue:   'text-azure-400 bg-azure-500/10',
    green:  'text-emerald-400 bg-emerald-500/10',
    amber:  'text-amber-400 bg-amber-500/10',
    rose:   'text-rose-400 bg-rose-500/10',
    violet: 'text-violet-400 bg-violet-500/10',
  };
  return (
    <div className="stat-card">
      <div className="flex items-center justify-between">
        <span className="label">{label}</span>
        {icon && <div className={cn('p-1.5 rounded-lg', colors[color])}><span className={colors[color].split(' ')[0]}>{icon}</span></div>}
      </div>
      <p className="font-display font-bold text-xl md:text-2xl text-primary">{value}</p>
      {sub && <p className="text-muted text-xs">{sub}</p>}
    </div>
  );
}

// ── Tanzania Grade Badge ──────────────────────────────────────────────────────
export function GradeBadge({ grade, pct }: { grade: string; pct: number }) {
  const color =
    grade === 'A' ? 'bg-emerald-500/15 text-emerald-400' :
    grade === 'B' ? 'bg-azure-500/15 text-azure-400' :
    grade === 'C' ? 'bg-amber-500/15 text-amber-400' :
    grade === 'D' ? 'bg-orange-500/15 text-orange-400' :
    'bg-rose-500/15 text-rose-400';
  return <span className={cn('badge font-mono', color)}>{grade} ({pct}%)</span>;
}
