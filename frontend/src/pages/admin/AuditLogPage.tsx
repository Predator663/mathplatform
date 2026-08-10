import { useState, Fragment } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ClipboardList, Search, ChevronLeft, ChevronRight, ChevronDown, ChevronUp } from 'lucide-react';
import { auditApi } from '../../api';
import type { AuditLog, PaginatedResponse } from '../../types';

const ACTION_COLORS: Record<string, string> = {
  create: 'bg-emerald-500/15 text-emerald-400',
  update: 'bg-blue-500/15 text-blue-400',
  delete: 'bg-red-500/15 text-red-400',
  login:  'bg-purple-500/15 text-purple-400',
  logout: 'bg-amber-500/15 text-amber-400',
};

function formatTs(ts: string) {
  return new Date(ts).toLocaleString('en-TZ', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function formatDiffValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) return value.length ? value.join(', ') : '—';
  return String(value);
}

function DiffRow({ field, change }: { field: string; change: { old: unknown; new: unknown } }) {
  return (
    <div className="flex items-start gap-2 py-1.5 px-3 rounded-lg bg-surface-900/60 text-xs">
      <span className="font-mono text-secondary min-w-[110px] flex-shrink-0">{field}</span>
      <span className="text-rose-400/90 line-through decoration-rose-500/50">{formatDiffValue(change.old)}</span>
      <span className="text-secondary flex-shrink-0">→</span>
      <span className="text-emerald-400 font-medium break-all">{formatDiffValue(change.new)}</span>
    </div>
  );
}

export default function AuditLogPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [action, setAction] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const pageSize = 30;

  const params: Record<string, unknown> = { page, page_size: pageSize };
  if (search) params.search = search;
  if (action) params.action = action;
  if (dateFrom) params.date_from = dateFrom;
  if (dateTo) params.date_to = dateTo;

  const { data, isLoading } = useQuery<PaginatedResponse<AuditLog>>({
    queryKey: ['audit-log', params],
    queryFn: () => auditApi.list(params).then(r => r.data),
    placeholderData: prev => prev,
  });

  const logs = data?.results ?? [];
  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-azure-500/15 flex items-center justify-center">
          <ClipboardList size={20} className="text-azure-400" />
        </div>
        <div>
          <h1 className="text-2xl font-display font-bold text-primary">Audit Log</h1>
          <p className="text-sm text-secondary">Read-only record of all platform mutations</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-surface-800 border border-surface rounded-2xl p-4 mb-4 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary" />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            placeholder="Search user, model, description…"
            className="w-full pl-8 pr-3 py-2 bg-surface-700 border border-surface rounded-xl text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
          />
        </div>
        <select
          value={action}
          onChange={e => { setAction(e.target.value); setPage(1); }}
          className="bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none"
        >
          <option value="">All actions</option>
          <option value="create">Create</option>
          <option value="update">Update</option>
          <option value="delete">Delete</option>
          <option value="login">Login</option>
          <option value="logout">Logout</option>
        </select>
        <input
          type="date"
          value={dateFrom}
          onChange={e => { setDateFrom(e.target.value); setPage(1); }}
          className="bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none"
          title="From date"
        />
        <input
          type="date"
          value={dateTo}
          onChange={e => { setDateTo(e.target.value); setPage(1); }}
          className="bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none"
          title="To date"
        />
        {(search || action || dateFrom || dateTo) && (
          <button
            onClick={() => { setSearch(''); setAction(''); setDateFrom(''); setDateTo(''); setPage(1); }}
            className="px-3 py-2 text-xs text-secondary hover:text-primary border border-surface rounded-xl"
          >
            Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-surface-800 border border-surface rounded-2xl overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-secondary text-sm">Loading…</div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center">
            <ClipboardList size={36} className="mx-auto mb-3 text-secondary opacity-30" />
            <p className="text-secondary">No audit log entries found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface">
                  <th className="w-8"></th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-secondary uppercase tracking-wider">Timestamp</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-secondary uppercase tracking-wider">User</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-secondary uppercase tracking-wider">Action</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-secondary uppercase tracking-wider">Model</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-secondary uppercase tracking-wider hidden md:table-cell">Description</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-secondary uppercase tracking-wider hidden lg:table-cell">IP</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log, i) => {
                  const changeCount = log.changes ? Object.keys(log.changes).length : 0;
                  const isExpanded = expandedId === log.id;
                  return (
                    <Fragment key={log.id}>
                      <tr
                        className={`border-b border-surface last:border-0 ${changeCount > 0 ? 'cursor-pointer hover:bg-surface-700/40' : ''} ${i % 2 === 0 ? '' : 'bg-surface-700/30'}`}
                        onClick={() => changeCount > 0 && setExpandedId(isExpanded ? null : log.id)}
                      >
                        <td className="pl-3">
                          {changeCount > 0 && (
                            isExpanded ? <ChevronUp size={13} className="text-secondary" /> : <ChevronDown size={13} className="text-secondary" />
                          )}
                        </td>
                        <td className="px-4 py-3 text-xs text-secondary whitespace-nowrap">{formatTs(log.timestamp)}</td>
                        <td className="px-4 py-3">
                          <div className="text-xs font-medium text-primary">{log.user_name || '—'}</div>
                          <div className="text-xs text-secondary">{log.user_email || '—'}</div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex px-2 py-0.5 rounded-lg text-xs font-medium ${ACTION_COLORS[log.action] ?? 'bg-surface-700 text-secondary'}`}>
                            {log.action_display}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-primary font-mono">
                          {log.model_name}{log.object_id && <span className="text-secondary"> #{log.object_id}</span>}
                        </td>
                        <td className="px-4 py-3 text-xs text-secondary max-w-xs truncate hidden md:table-cell">{log.description}</td>
                        <td className="px-4 py-3 text-xs text-secondary font-mono hidden lg:table-cell">{log.ip_address ?? '—'}</td>
                      </tr>
                      {isExpanded && log.changes && (
                        <tr className="bg-surface-900/40 border-b border-surface last:border-0">
                          <td colSpan={7} className="px-4 py-3">
                            <div className="flex flex-col gap-1.5 max-w-2xl">
                              <p className="text-[11px] text-secondary uppercase tracking-wider font-semibold mb-1">
                                {changeCount} field{changeCount !== 1 ? 's' : ''} changed
                              </p>
                              {Object.entries(log.changes).map(([field, change]) => (
                                <DiffRow key={field} field={field} change={change} />
                              ))}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-xs text-secondary">
            Page {page} of {totalPages} · {data?.count ?? 0} total entries
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-2 rounded-xl border border-surface text-secondary hover:text-primary disabled:opacity-40 transition-colors"
            >
              <ChevronLeft size={15} />
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-2 rounded-xl border border-surface text-secondary hover:text-primary disabled:opacity-40 transition-colors"
            >
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
