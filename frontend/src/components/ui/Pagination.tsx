import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { cn } from '../../utils';

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
  className?: string;
}

export function Pagination({ page, pageSize, total, onChange, className }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  // Build page numbers with ellipsis
  const getPages = (): (number | 'ellipsis')[] => {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
    const pages: (number | 'ellipsis')[] = [];
    if (page <= 4) {
      for (let i = 1; i <= 5; i++) pages.push(i);
      pages.push('ellipsis');
      pages.push(totalPages);
    } else if (page >= totalPages - 3) {
      pages.push(1);
      pages.push('ellipsis');
      for (let i = totalPages - 4; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      pages.push('ellipsis');
      for (let i = page - 1; i <= page + 1; i++) pages.push(i);
      pages.push('ellipsis');
      pages.push(totalPages);
    }
    return pages;
  };

  const btn = (active: boolean) =>
    cn(
      'w-8 h-8 flex items-center justify-center rounded-lg text-xs font-display font-medium transition-all',
      active
        ? 'bg-azure-500 text-white shadow-sm'
        : 'text-secondary hover:text-primary hover:bg-surface-700'
    );

  const navBtn = (disabled: boolean) =>
    cn(
      'w-8 h-8 flex items-center justify-center rounded-lg transition-all',
      disabled
        ? 'text-secondary opacity-40 cursor-not-allowed'
        : 'text-secondary hover:text-primary hover:bg-surface-700'
    );

  return (
    <div className={cn('flex items-center justify-between gap-4 py-3 px-1', className)}>
      <p className="text-xs text-secondary hidden sm:block">
        {from}–{to} of <span className="text-primary">{total}</span>
      </p>
      <div className="flex items-center gap-1 mx-auto sm:mx-0">
        <button className={navBtn(page === 1)} onClick={() => onChange(1)} disabled={page === 1} title="First page">
          <ChevronsLeft size={14} />
        </button>
        <button className={navBtn(page === 1)} onClick={() => onChange(page - 1)} disabled={page === 1} title="Previous page">
          <ChevronLeft size={14} />
        </button>

        {getPages().map((p, i) =>
          p === 'ellipsis' ? (
            <span key={`e${i}`} className="w-8 text-center text-secondary text-xs">…</span>
          ) : (
            <button key={p} className={btn(p === page)} onClick={() => onChange(p as number)}>
              {p}
            </button>
          )
        )}

        <button className={navBtn(page === totalPages)} onClick={() => onChange(page + 1)} disabled={page === totalPages} title="Next page">
          <ChevronRight size={14} />
        </button>
        <button className={navBtn(page === totalPages)} onClick={() => onChange(totalPages)} disabled={page === totalPages} title="Last page">
          <ChevronsRight size={14} />
        </button>
      </div>
    </div>
  );
}
