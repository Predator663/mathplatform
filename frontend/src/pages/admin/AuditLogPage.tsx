import { useMemo, useState, Fragment } from 'react';
import { useQuery } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  ClipboardList, Search, ChevronLeft, ChevronRight, ChevronDown, ChevronUp,
  Download, FileDown, X, History, UserRound, MapPin, Fingerprint, Layers,
} from 'lucide-react';
import { auditApi } from '../../api';
import { Modal, Button, Select, LoadingPage, EmptyState } from '../../components/ui';
import { downloadBlob, blobErrorMessage } from '../../utils';
import type { AuditLog, AuditLogFacets, AuditLogStats, PaginatedResponse } from '../../types';

const ACTION_COLORS: Record<string, string> = {
  create: 'bg-emerald-500/15 text-emerald-400',
  update: 'bg-blue-500/15 text-blue-400',
  delete: 'bg-red-500/15 text-red-400',
  login:  'bg-purple-500/15 text-purple-400',
  logout: 'bg-amber-500/15 text-amber-400',
};

const ACTION_DOT: Record<string, string> = {
  create: 'bg-emerald-400', update: 'bg-blue-400', delete: 'bg-red-400',
  login: 'bg-purple-400', logout: 'bg-amber-400',
};

function formatTs(ts: string) {
  return new Date(ts).toLocaleString('en-TZ', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function dateOnly(ts: string) {
  return ts.slice(0, 10);
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

function StatCard({ label, value, dotClass }: { label: string; value: number; dotClass?: string }) {
  return (
    <div className="bg-surface-800 border border-surface rounded-xl px-4 py-3 flex-1 min-w-[110px]">
      <div className="flex items-center gap-1.5 mb-1">
        {dotClass && <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />}
        <p className="text-[11px] text-secondary uppercase tracking-wider font-semibold">{label}</p>
      </div>
      <p className="text-xl font-display font-bold text-primary">{value}</p>
    </div>
  );
}

// ── Detail drawer: trace an entry deeply ────────────────────────────────────

function LogDetailModal({ log, onClose }: { log: AuditLog; onClose: () => void }) {
  const [tab, setTab] = useState<'diff' | 'object' | 'user'>('diff');
  const changeCount = log.changes ? Object.keys(log.changes).length : 0;

  const { data: objectHistory, isLoading: objectLoading } = useQuery<PaginatedResponse<AuditLog>>({
    queryKey: ['audit-object-history', log.model_name, log.object_id],
    queryFn: () => auditApi.list({
      model_name: log.model_name, object_id: log.object_id, page_size: 50,
    }).then(r => r.data),
    enabled: tab === 'object' && !!log.object_id,
  });

  const { data: userActivity, isLoading: userLoading } = useQuery<PaginatedResponse<AuditLog>>({
    queryKey: ['audit-user-activity', log.user, dateOnly(log.timestamp)],
    queryFn: () => auditApi.list({
      user: log.user, date_from: dateOnly(log.timestamp), date_to: dateOnly(log.timestamp), page_size: 50,
    }).then(r => r.data),
    enabled: tab === 'user' && !!log.user,
  });

  async function handleDownloadCard() {
    try {
      const res = await auditApi.downloadCard(log.id);
      downloadBlob(res.data, `audit_log_card_${log.id}.pdf`);
      toast.success('Card downloaded.');
    } catch (e) {
      toast.error(await blobErrorMessage(e, 'Could not download this card.'));
    }
  }

  return (
    <Modal open onClose={onClose} title={`Audit Entry #${log.id}`} size="lg">
      <div className="flex flex-col gap-4 -mt-1">
        {/* Summary header */}
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`inline-flex px-2 py-0.5 rounded-lg text-xs font-medium ${ACTION_COLORS[log.action] ?? 'bg-surface-700 text-secondary'}`}>
                {log.action_display}
              </span>
              <span className="text-sm font-mono text-primary">
                {log.model_name}{log.object_id && <span className="text-secondary"> #{log.object_id}</span>}
              </span>
            </div>
            <p className="text-xs text-secondary">{formatTs(log.timestamp)}</p>
          </div>
          <Button size="sm" variant="secondary" onClick={handleDownloadCard}>
            <Download size={14} /> Download Card (PDF)
          </Button>
        </div>

        {/* Meta grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          <div className="bg-surface-900/50 rounded-lg px-3 py-2">
            <p className="text-secondary mb-0.5 flex items-center gap-1"><UserRound size={11} /> User</p>
            <p className="text-primary font-medium truncate">{log.user_name || '—'}</p>
            <p className="text-secondary truncate">{log.user_email || '—'}</p>
          </div>
          <div className="bg-surface-900/50 rounded-lg px-3 py-2">
            <p className="text-secondary mb-0.5 flex items-center gap-1"><MapPin size={11} /> IP Address</p>
            <p className="text-primary font-mono">{log.ip_address || '—'}</p>
          </div>
          <div className="bg-surface-900/50 rounded-lg px-3 py-2">
            <p className="text-secondary mb-0.5 flex items-center gap-1"><Fingerprint size={11} /> Object ID</p>
            <p className="text-primary font-mono">{log.object_id || '—'}</p>
          </div>
          <div className="bg-surface-900/50 rounded-lg px-3 py-2">
            <p className="text-secondary mb-0.5 flex items-center gap-1"><Layers size={11} /> Fields Changed</p>
            <p className="text-primary font-medium">{changeCount}</p>
          </div>
        </div>

        {log.description && (
          <p className="text-xs font-mono text-secondary bg-surface-900/40 rounded-lg px-3 py-2">{log.description}</p>
        )}

        {/* Tabs */}
        <div className="flex gap-1 border-b border-surface">
          {[
            { key: 'diff' as const, label: `Diff (${changeCount})` },
            { key: 'object' as const, label: 'Object History', disabled: !log.object_id },
            { key: 'user' as const, label: 'Same-Day User Activity', disabled: !log.user },
          ].map(t => (
            <button
              key={t.key}
              disabled={t.disabled}
              onClick={() => setTab(t.key)}
              className={`px-3 py-2 text-xs font-medium border-b-2 -mb-px transition-colors disabled:opacity-30 disabled:cursor-not-allowed ${
                tab === t.key ? 'border-azure-400 text-primary' : 'border-transparent text-secondary hover:text-primary'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="min-h-[120px]">
          {tab === 'diff' && (
            changeCount === 0 ? (
              <p className="text-xs text-secondary py-4 text-center">No field-level changes recorded for this entry.</p>
            ) : (
              <div className="flex flex-col gap-1.5">
                {Object.entries(log.changes!).map(([field, change]) => (
                  <DiffRow key={field} field={field} change={change} />
                ))}
              </div>
            )
          )}

          {tab === 'object' && (
            objectLoading ? (
              <p className="text-xs text-secondary py-4 text-center">Loading object history…</p>
            ) : !objectHistory || objectHistory.results.length === 0 ? (
              <p className="text-xs text-secondary py-4 text-center">No other entries found for this object.</p>
            ) : (
              <div className="flex flex-col gap-1.5">
                <p className="text-[11px] text-secondary uppercase tracking-wider font-semibold mb-0.5">
                  <History size={11} className="inline mr-1" />
                  Full timeline for {log.model_name} #{log.object_id} ({objectHistory.count} entries)
                </p>
                {objectHistory.results.map(entry => (
                  <div key={entry.id}
                    className={`flex items-center gap-2 text-xs rounded-lg px-3 py-1.5 ${entry.id === log.id ? 'bg-azure-500/10 border border-azure-500/30' : 'bg-surface-900/50'}`}>
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${ACTION_DOT[entry.action] ?? 'bg-secondary'}`} />
                    <span className="text-secondary whitespace-nowrap">{formatTs(entry.timestamp)}</span>
                    <span className={`font-medium ${ACTION_COLORS[entry.action]?.split(' ')[1] ?? 'text-primary'}`}>{entry.action_display}</span>
                    <span className="text-secondary truncate flex-1">by {entry.user_name || entry.user_email || '—'}</span>
                    {entry.changes && <span className="text-secondary flex-shrink-0">{Object.keys(entry.changes).length} field(s)</span>}
                  </div>
                ))}
              </div>
            )
          )}

          {tab === 'user' && (
            userLoading ? (
              <p className="text-xs text-secondary py-4 text-center">Loading user activity…</p>
            ) : !userActivity || userActivity.results.length === 0 ? (
              <p className="text-xs text-secondary py-4 text-center">No other activity found for this user on this day.</p>
            ) : (
              <div className="flex flex-col gap-1.5">
                <p className="text-[11px] text-secondary uppercase tracking-wider font-semibold mb-0.5">
                  Everything {log.user_name || log.user_email} did on {dateOnly(log.timestamp)} ({userActivity.count} entries)
                </p>
                {userActivity.results.map(entry => (
                  <div key={entry.id}
                    className={`flex items-center gap-2 text-xs rounded-lg px-3 py-1.5 ${entry.id === log.id ? 'bg-azure-500/10 border border-azure-500/30' : 'bg-surface-900/50'}`}>
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${ACTION_DOT[entry.action] ?? 'bg-secondary'}`} />
                    <span className="text-secondary whitespace-nowrap">{formatTs(entry.timestamp)}</span>
                    <span className={`font-medium ${ACTION_COLORS[entry.action]?.split(' ')[1] ?? 'text-primary'}`}>{entry.action_display}</span>
                    <span className="text-secondary truncate flex-1">
                      {entry.model_name}{entry.object_id && ` #${entry.object_id}`}
                    </span>
                  </div>
                ))}
              </div>
            )
          )}
        </div>
      </div>
    </Modal>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function AuditLogPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [action, setAction] = useState('');
  const [modelName, setModelName] = useState('');
  const [userId, setUserId] = useState('');
  const [objectId, setObjectId] = useState('');
  const [ipAddress, setIpAddress] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detailLog, setDetailLog] = useState<AuditLog | null>(null);
  const [exporting, setExporting] = useState<'csv' | 'cards' | null>(null);
  const pageSize = 30;

  const filterParams: Record<string, unknown> = {};
  if (search) filterParams.search = search;
  if (action) filterParams.action = action;
  if (modelName) filterParams.model_name = modelName;
  if (userId) filterParams.user = userId;
  if (objectId) filterParams.object_id = objectId;
  if (ipAddress) filterParams.ip_address = ipAddress;
  if (dateFrom) filterParams.date_from = dateFrom;
  if (dateTo) filterParams.date_to = dateTo;

  const hasFilters = Object.keys(filterParams).length > 0;
  const params = { ...filterParams, page, page_size: pageSize };

  const { data, isLoading } = useQuery<PaginatedResponse<AuditLog>>({
    queryKey: ['audit-log', params],
    queryFn: () => auditApi.list(params).then(r => r.data),
    placeholderData: prev => prev,
  });

  const { data: facets } = useQuery<AuditLogFacets>({
    queryKey: ['audit-log-facets'],
    queryFn: () => auditApi.facets().then(r => r.data),
    staleTime: 5 * 60 * 1000,
  });

  const { data: stats } = useQuery<AuditLogStats>({
    queryKey: ['audit-log-stats', filterParams],
    queryFn: () => auditApi.stats(filterParams).then(r => r.data),
    placeholderData: prev => prev,
  });

  const logs = data?.results ?? [];
  const totalPages = data ? Math.ceil(data.count / pageSize) : 1;

  const modelOptions = useMemo(
    () => [{ value: '', label: 'All models' }, ...(facets?.models ?? []).map(m => ({ value: m, label: m }))],
    [facets],
  );
  const userOptions = useMemo(
    () => [{ value: '', label: 'All users' }, ...(facets?.users ?? []).map(u => ({ value: u.id, label: u.name }))],
    [facets],
  );

  function clearFilters() {
    setSearch(''); setAction(''); setModelName(''); setUserId('');
    setObjectId(''); setIpAddress(''); setDateFrom(''); setDateTo('');
    setPage(1);
  }

  async function handleExportCsv() {
    setExporting('csv');
    try {
      const res = await auditApi.exportCsv(filterParams);
      downloadBlob(res.data, 'audit_log_export.csv');
      toast.success('CSV exported.');
    } catch (e) {
      toast.error(await blobErrorMessage(e, 'CSV export failed.'));
    } finally {
      setExporting(null);
    }
  }

  async function handleExportCards() {
    setExporting('cards');
    try {
      const res = await auditApi.downloadCardsBatch(filterParams);
      downloadBlob(res.data, 'audit_log_cards.pdf');
      toast.success('Cards downloaded.');
    } catch (e) {
      toast.error(await blobErrorMessage(e, 'Card export failed — try narrowing your filters.'));
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 mb-6 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-azure-500/15 flex items-center justify-center">
            <ClipboardList size={20} className="text-azure-400" />
          </div>
          <div>
            <h1 className="text-2xl font-display font-bold text-primary">Audit Log</h1>
            <p className="text-sm text-secondary">Deep-trace record of every platform mutation · Super Admin only</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" loading={exporting === 'csv'} onClick={handleExportCsv}>
            <FileDown size={14} /> Export CSV
          </Button>
          <Button variant="secondary" size="sm" loading={exporting === 'cards'} onClick={handleExportCards}>
            <Download size={14} /> Export Cards (PDF)
          </Button>
        </div>
      </div>

      {/* Stat cards */}
      {stats && (
        <div className="flex flex-wrap gap-3 mb-4">
          <StatCard label="Matching Entries" value={stats.total} />
          <StatCard label="Creates" value={stats.by_action.create ?? 0} dotClass="bg-emerald-400" />
          <StatCard label="Updates" value={stats.by_action.update ?? 0} dotClass="bg-blue-400" />
          <StatCard label="Deletes" value={stats.by_action.delete ?? 0} dotClass="bg-red-400" />
          <StatCard label="Logins" value={stats.by_action.login ?? 0} dotClass="bg-purple-400" />
          <StatCard label="Logouts" value={stats.by_action.logout ?? 0} dotClass="bg-amber-400" />
        </div>
      )}

      {/* Filters */}
      <div className="bg-surface-800 border border-surface rounded-2xl p-4 mb-4 flex flex-wrap gap-3 items-end">
        <div className="relative flex-1 min-w-48">
          <label className="text-[11px] text-secondary uppercase tracking-wider font-semibold block mb-1">Search</label>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary" />
            <input
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              placeholder="Description, email, model…"
              className="w-full pl-8 pr-3 py-2 bg-surface-700 border border-surface rounded-xl text-sm text-primary focus:outline-none focus:ring-1 focus:ring-azure-500"
            />
          </div>
        </div>
        <div className="min-w-[140px]">
          <Select label="Action" value={action} onChange={e => { setAction(e.target.value); setPage(1); }}
            options={[{ value: '', label: 'All actions' }, ...(facets?.actions ?? [
              { value: 'create', label: 'Create' }, { value: 'update', label: 'Update' },
              { value: 'delete', label: 'Delete' }, { value: 'login', label: 'Login' }, { value: 'logout', label: 'Logout' },
            ])]} />
        </div>
        <div className="min-w-[150px]">
          <Select label="Model" value={modelName} onChange={e => { setModelName(e.target.value); setPage(1); }} options={modelOptions} />
        </div>
        <div className="min-w-[170px]">
          <Select label="User" value={userId} onChange={e => { setUserId(e.target.value); setPage(1); }} options={userOptions} />
        </div>
        <div className="min-w-[110px]">
          <label className="text-[11px] text-secondary uppercase tracking-wider font-semibold block mb-1">Object ID</label>
          <input value={objectId} onChange={e => { setObjectId(e.target.value); setPage(1); }} placeholder="e.g. 42"
            className="w-full px-3 py-2 bg-surface-700 border border-surface rounded-xl text-sm text-primary focus:outline-none" />
        </div>
        <div className="min-w-[140px]">
          <label className="text-[11px] text-secondary uppercase tracking-wider font-semibold block mb-1">IP Address</label>
          <input value={ipAddress} onChange={e => { setIpAddress(e.target.value); setPage(1); }} placeholder="10.0.0.1"
            className="w-full px-3 py-2 bg-surface-700 border border-surface rounded-xl text-sm text-primary font-mono focus:outline-none" />
        </div>
        <div>
          <label className="text-[11px] text-secondary uppercase tracking-wider font-semibold block mb-1">From</label>
          <input type="date" value={dateFrom} onChange={e => { setDateFrom(e.target.value); setPage(1); }}
            className="bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none" />
        </div>
        <div>
          <label className="text-[11px] text-secondary uppercase tracking-wider font-semibold block mb-1">To</label>
          <input type="date" value={dateTo} onChange={e => { setDateTo(e.target.value); setPage(1); }}
            className="bg-surface-700 border border-surface rounded-xl px-3 py-2 text-sm text-primary focus:outline-none" />
        </div>
        {hasFilters && (
          <button onClick={clearFilters}
            className="px-3 py-2 text-xs text-secondary hover:text-primary border border-surface rounded-xl flex items-center gap-1">
            <X size={12} /> Clear
          </button>
        )}
      </div>

      {/* Table */}
      <div className="bg-surface-800 border border-surface rounded-2xl overflow-hidden">
        {isLoading ? (
          <LoadingPage />
        ) : logs.length === 0 ? (
          <EmptyState icon={<ClipboardList size={36} />} title="No audit log entries found"
            message="Nothing matches these filters yet." />
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
                  <th className="w-10"></th>
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
                        <td className="px-2 py-3">
                          <button
                            onClick={e => { e.stopPropagation(); setDetailLog(log); }}
                            className="text-xs text-azure-400 hover:text-azure-300 font-medium whitespace-nowrap"
                          >
                            Trace →
                          </button>
                        </td>
                      </tr>
                      {isExpanded && log.changes && (
                        <tr className="bg-surface-900/40 border-b border-surface last:border-0">
                          <td colSpan={8} className="px-4 py-3">
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

      {detailLog && <LogDetailModal log={detailLog} onClose={() => setDetailLog(null)} />}
    </div>
  );
}
