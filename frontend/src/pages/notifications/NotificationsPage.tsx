import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, Link } from 'react-router-dom';
import { Bell, CheckCheck, AlertTriangle, TrendingDown, BookOpen, ShieldAlert, Sparkles, Settings } from 'lucide-react';
import { notificationsApi } from '../../api';
import { LoadingPage, EmptyState, Button, Pagination } from '../../components/ui';
import type { NotificationLogEntry, PaginatedResponse } from '../../types';

const CATEGORY_META: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
  at_risk:         { icon: AlertTriangle, color: '#e11d48', bg: '#fef2f2' },
  risk_critical:   { icon: TrendingDown,  color: '#e11d48', bg: '#fef2f2' },
  exam_published:  { icon: BookOpen,      color: '#3b82f6', bg: '#eff6ff' },
  integrity_flag:  { icon: ShieldAlert,   color: '#b45309', bg: '#fffbeb' },
  daily_digest:    { icon: Sparkles,      color: '#8b5cf6', bg: '#f5f3ff' },
};

// Best-effort reconstruction of "where does this notification point to" from
// its category + related_object_type/id — the backend only logs the loose
// pointer (kept intentionally simple, see NotificationLog docstring), so the
// exact destination is resolved here rather than stored redundantly server-side.
function resolveLink(entry: NotificationLogEntry): string | null {
  const id = entry.related_object_id;
  if (id == null) return null;
  switch (entry.category) {
    case 'at_risk':
    case 'risk_critical':
      return `/analytics/student/${id}`;
    case 'exam_published':
      return `/exams/${id}`;
    case 'integrity_flag':
      return '/analytics/integrity';
    case 'daily_digest':
      return '/dashboard';
    default:
      return null;
  }
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString('en-TZ', { month: 'short', day: 'numeric' });
}

export default function NotificationsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const { data, isLoading } = useQuery<PaginatedResponse<NotificationLogEntry>>({
    queryKey: ['notification-history', page, unreadOnly],
    queryFn: () => notificationsApi.history({ page, unread_only: unreadOnly || undefined }).then(r => r.data),
  });

  const markReadMutation = useMutation({
    mutationFn: (id?: number) => notificationsApi.markRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notification-history'] });
      qc.invalidateQueries({ queryKey: ['notifications-unread-count'] });
    },
  });

  const notifications = data?.results ?? [];
  const total = data?.count ?? 0;

  const handleClick = (entry: NotificationLogEntry) => {
    if (!entry.read_at) markReadMutation.mutate(entry.id);
    const link = resolveLink(entry);
    if (link) navigate(link);
  };

  return (
    <div className="flex flex-col gap-6 page-enter">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h1 className="page-title flex items-center gap-2">
            <Bell size={22} className="text-azure-400" />
            Notifications
          </h1>
          <p className="text-muted text-sm mt-1">
            Everything that's been emailed to you, kept here too in case you don't have your inbox open.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => markReadMutation.mutate(undefined)}>
            <CheckCheck size={14} /> Mark all read
          </Button>
          <Link to="/settings/notifications">
            <Button variant="secondary" size="sm"><Settings size={14} /> Preferences</Button>
          </Link>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => { setUnreadOnly(false); setPage(1); }}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${!unreadOnly ? 'border-azure-500 bg-azure-500/10 text-azure-400' : 'border-surface text-secondary'}`}
        >
          All
        </button>
        <button
          onClick={() => { setUnreadOnly(true); setPage(1); }}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${unreadOnly ? 'border-azure-500 bg-azure-500/10 text-azure-400' : 'border-surface text-secondary'}`}
        >
          Unread only
        </button>
      </div>

      {isLoading ? (
        <LoadingPage />
      ) : notifications.length === 0 ? (
        <EmptyState
          icon={<Bell size={40} />}
          title={unreadOnly ? "You're all caught up" : 'No notifications yet'}
          message={unreadOnly ? 'No unread notifications right now.' : "Alerts about at-risk students, published exams, and grading anomalies will show up here as they're emailed to you."}
        />
      ) : (
        <>
          <div className="flex flex-col gap-2">
            {notifications.map(entry => {
              const meta = CATEGORY_META[entry.category] ?? CATEGORY_META.daily_digest;
              const Icon = meta.icon;
              const unread = !entry.read_at;
              return (
                <button
                  key={entry.id}
                  onClick={() => handleClick(entry)}
                  className={`card p-4 flex items-start gap-3 text-left transition-colors hover:border-azure-500/40 ${unread ? 'border-azure-500/30' : ''}`}
                >
                  <div
                    className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: meta.bg, color: meta.color }}
                  >
                    <Icon size={16} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className={`text-sm ${unread ? 'font-display font-semibold text-primary' : 'text-secondary'}`}>
                        {entry.subject}
                      </p>
                      {unread && <span className="w-1.5 h-1.5 rounded-full bg-azure-400 flex-shrink-0" />}
                    </div>
                    {entry.summary && <p className="text-xs text-muted mt-0.5 truncate">{entry.summary}</p>}
                  </div>
                  <span className="text-[11px] text-muted flex-shrink-0 whitespace-nowrap">{timeAgo(entry.sent_at)}</span>
                </button>
              );
            })}
          </div>
          <Pagination page={page} pageSize={20} total={total} onChange={setPage} />
        </>
      )}
    </div>
  );
}
