import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Bell, Mail, Send } from 'lucide-react';
import toast from 'react-hot-toast';
import { notificationsApi } from '../../api';
import { LoadingPage, Button, Select } from '../../components/ui';
import { useAuthStore } from '../../store/auth';
import type { NotificationPreferenceItem, NotificationFrequency } from '../../types';

const FREQUENCY_OPTIONS: { value: NotificationFrequency; label: string }[] = [
  { value: 'immediate', label: 'Email me immediately' },
  { value: 'digest', label: 'Include in daily digest' },
  { value: 'off', label: 'Turn off' },
];

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  at_risk: 'A student\'s recent average drops below the at-risk threshold, or their scores are declining.',
  risk_critical: 'A student\'s composite risk score (trend, volatility, topic gaps, pass margin combined) reaches critical.',
  exam_published: 'A new exam becomes visible to students and parents.',
  integrity_flag: 'The daily scan finds a suspicious score edit (admins only).',
};

export default function NotificationSettingsPage() {
  const qc = useQueryClient();
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'super_admin';
  const [pendingChanges, setPendingChanges] = useState<Record<string, NotificationFrequency>>({});

  const { data, isLoading } = useQuery<NotificationPreferenceItem[]>({
    queryKey: ['notification-preferences'],
    queryFn: () => notificationsApi.preferences().then(r => r.data),
  });

  const saveMutation = useMutation({
    mutationFn: (updates: { category: string; frequency: string }[]) => notificationsApi.updatePreferences(updates),
    onSuccess: () => {
      toast.success('Notification preferences saved.');
      setPendingChanges({});
      qc.invalidateQueries({ queryKey: ['notification-preferences'] });
    },
    onError: () => toast.error('Failed to save preferences.'),
  });

  const testEmailMutation = useMutation({
    mutationFn: () => notificationsApi.testEmail(),
    onSuccess: (res) => toast.success(res.data?.detail ?? 'Test email sent.'),
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ?? 'Failed to send test email.');
    },
  });

  const items = data ?? [];
  const effectiveFrequency = (item: NotificationPreferenceItem) => pendingChanges[item.category] ?? item.frequency;
  const hasChanges = Object.keys(pendingChanges).length > 0;

  const handleChange = (category: string, frequency: NotificationFrequency) => {
    setPendingChanges(prev => ({ ...prev, [category]: frequency }));
  };

  const handleSave = () => {
    const updates = Object.entries(pendingChanges).map(([category, frequency]) => ({ category, frequency }));
    if (updates.length) saveMutation.mutate(updates);
  };

  return (
    <div className="flex flex-col gap-6 page-enter max-w-2xl">
      <div>
        <h1 className="page-title flex items-center gap-2">
          <Bell size={22} className="text-azure-400" />
          Notification Settings
        </h1>
        <p className="text-muted text-sm mt-1">
          Choose how you want to hear about at-risk students, published exams, and grading anomalies —
          emailed immediately, bundled into one daily summary, or off entirely.
        </p>
      </div>

      {isLoading ? (
        <LoadingPage />
      ) : (
        <>
          <div className="card divide-y divide-surface" style={{ borderColor: 'var(--border)' }}>
            {items.map(item => (
              <div key={item.category} className="p-4 md:p-5 flex items-center justify-between gap-4 flex-wrap">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-display font-medium text-primary">{item.category_label}</p>
                  {CATEGORY_DESCRIPTIONS[item.category] && (
                    <p className="text-xs text-muted mt-0.5">{CATEGORY_DESCRIPTIONS[item.category]}</p>
                  )}
                </div>
                <div className="w-56 flex-shrink-0">
                  <Select
                    value={effectiveFrequency(item)}
                    onChange={e => handleChange(item.category, e.target.value as NotificationFrequency)}
                    options={FREQUENCY_OPTIONS}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between gap-3 flex-wrap">
            {isAdmin ? (
              <Button variant="secondary" onClick={() => testEmailMutation.mutate()} loading={testEmailMutation.isPending}>
                <Send size={14} /> Send test email to myself
              </Button>
            ) : <span />}
            <Button onClick={handleSave} disabled={!hasChanges} loading={saveMutation.isPending}>
              <Mail size={14} /> Save Preferences
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
