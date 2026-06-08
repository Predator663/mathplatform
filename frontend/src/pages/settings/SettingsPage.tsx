import { useState, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import {
  User, Lock, Database, Wifi, WifiOff, RefreshCw, Trash2,
  Settings, Globe, Image, Type, Layout, Hash, Eye, EyeOff,
  Monitor, Save, LogIn,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { authApi } from '../../api';
import api from '../../api';
import { useAuthStore } from '../../store/auth';
import { useSync } from '../../hooks/usePWASync';
import { useSiteSettingsStore, PAGE_REGISTRY } from '../../store/siteSettings';
import { Button, Input } from '../../components/ui';
import { getAllSyncMeta, clearAllCaches, clearPendingQueue, getPendingScoreCount } from '../../db';

interface ProfileForm { first_name: string; last_name: string; phone: string; }
interface PasswordForm { old_password: string; new_password: string; confirm_password: string; }

interface SiteSettingsForm {
  platform_name: string;
  platform_subtitle: string;
  logo_letter: string;
  logo_url: string;
  favicon_url: string;
  footer_text: string;
  login_tagline: string;
  login_welcome: string;
  login_bg_gradient: boolean;
}

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super Admin', teacher: 'Teacher', student: 'Student', parent: 'Parent',
};

const PAGE_SIZE_OPTIONS = [5, 10, 15, 20, 25, 50];

export default function SettingsPage() {
  const { user, updateUser } = useAuthStore();
  const { isOnline, pendingCount, isSyncing, lastSynced, syncNow } = useSync();
  const { settings, setSettings, getPage } = useSiteSettingsStore();
  const isSuperAdmin = user?.role === 'super_admin';

  type TabId = 'profile' | 'password' | 'offline' | 'site';
  const [activeTab, setActiveTab] = useState<TabId>('profile');
  const [syncMeta, setSyncMeta] = useState<{ entity: string; last_synced: number; record_count: number }[]>([]);
  const [loadingMeta, setLoadingMeta] = useState(false);
  const [pendingScoreCount, setPendingCount] = useState(0);
  const [pageSizes, setPageSizes] = useState<Record<string, number>>({});
  const [pageEnabled, setPageEnabled] = useState<Record<string, boolean>>({});
  const [savingSite, setSavingSite] = useState(false);
  const [faviconPreview, setFaviconPreview] = useState('');
  const [logoPreview, setLogoPreview] = useState('');

  // Load current site settings into page size/enabled state
  useEffect(() => {
    const sizes: Record<string, number> = {};
    const enabled: Record<string, boolean> = {};
    PAGE_REGISTRY.forEach(({ key }) => {
      sizes[key] = getPage(key).page_size;
      enabled[key] = getPage(key).enabled;
    });
    setPageSizes(sizes);
    setPageEnabled(enabled);
  }, [settings]);

  const { register: regProfile, handleSubmit: handleProfile, formState: { errors: pe } } = useForm<ProfileForm>({
    defaultValues: { first_name: user?.first_name ?? '', last_name: user?.last_name ?? '', phone: user?.phone ?? '' },
  });
  const { register: regPw, handleSubmit: handlePw, reset: resetPw, watch, formState: { errors: pwe } } = useForm<PasswordForm>();
  const newPw = watch('new_password');

  const siteForm = useForm<SiteSettingsForm>({
    defaultValues: {
      platform_name: settings.platform_name,
      platform_subtitle: settings.platform_subtitle,
      logo_letter: settings.logo_letter,
      logo_url: settings.logo_url,
      favicon_url: settings.favicon_url,
      footer_text: settings.footer_text,
      login_tagline: settings.login_tagline,
      login_welcome: settings.login_welcome,
      login_bg_gradient: settings.login_bg_gradient,
    },
  });

  // Sync site form with store when store loads
  useEffect(() => {
    siteForm.reset({
      platform_name: settings.platform_name,
      platform_subtitle: settings.platform_subtitle,
      logo_letter: settings.logo_letter,
      logo_url: settings.logo_url,
      favicon_url: settings.favicon_url,
      footer_text: settings.footer_text,
      login_tagline: settings.login_tagline,
      login_welcome: settings.login_welcome,
      login_bg_gradient: settings.login_bg_gradient,
    });
    setFaviconPreview(settings.favicon_url);
    setLogoPreview(settings.logo_url);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.platform_name, settings.platform_subtitle, settings.logo_letter,
      settings.logo_url, settings.favicon_url, settings.footer_text,
      settings.login_tagline, settings.login_welcome, settings.login_bg_gradient]);

  const profileMutation = useMutation({
    mutationFn: (data: ProfileForm) => authApi.updateMe(data).then(r => r.data),
    onSuccess: (data) => { updateUser(data); toast.success('Profile updated'); },
    onError: () => toast.error('Failed to update profile'),
  });

  const passwordMutation = useMutation({
    mutationFn: (data: PasswordForm) => authApi.changePassword(data),
    onSuccess: () => { resetPw(); toast.success('Password changed'); },
    onError: (err: unknown) => {
      const e = err as { response?: { data?: Record<string, string[]> } };
      const msgs = e?.response?.data;
      if (msgs) Object.values(msgs).flat().forEach(m => toast.error(String(m)));
      else toast.error('Failed to change password');
    },
  });

  const loadOfflineMeta = async () => {
    setLoadingMeta(true);
    try {
      const [meta, count] = await Promise.all([getAllSyncMeta(), getPendingScoreCount()]);
      setSyncMeta(meta);
      setPendingCount(count);
    } catch { toast.error('Could not read offline data'); }
    finally { setLoadingMeta(false); }
  };

  const handleClearCache = async () => {
    if (!confirm('Clear all offline cached data? You will need to be online to reload it.')) return;
    await clearAllCaches();
    setSyncMeta([]);
    toast.success('Offline cache cleared');
  };

  const handleClearPending = async () => {
    if (!confirm('Discard all pending offline changes? This cannot be undone.')) return;
    await clearPendingQueue();
    setPendingCount(0);
    toast.success('Pending queue cleared');
  };

  const handleSaveSiteSettings = async (formData: SiteSettingsForm) => {
    setSavingSite(true);
    try {
      const page_settings: Record<string, { enabled: boolean; page_size: number }> = {};
      PAGE_REGISTRY.forEach(({ key }) => {
        page_settings[key] = {
          enabled: pageEnabled[key] ?? true,
          page_size: pageSizes[key] ?? 20,
        };
      });

      const payload = { ...formData, page_settings };
      const res = await api.patch('/auth/settings/', payload);
      setSettings(res.data);

      // Apply favicon dynamically
      if (res.data.favicon_url) {
        let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
        if (!link) { link = document.createElement('link'); link.rel = 'icon'; document.head.appendChild(link); }
        link.href = res.data.favicon_url;
      }
      // Apply title dynamically
      if (res.data.platform_name) {
        document.title = res.data.platform_subtitle
          ? `${res.data.platform_name} — ${res.data.platform_subtitle}`
          : res.data.platform_name;
      }

      toast.success('Site settings saved');
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number; data?: unknown }; message?: string };
      const status = axiosErr?.response?.status;
      const data = axiosErr?.response?.data;

      console.error('Site settings save error:', axiosErr?.response ?? axiosErr?.message ?? err);

      if (status === 403) {
        toast.error('Permission denied — Super Admin only');
      } else if (data && typeof data === 'object' && !Array.isArray(data)) {
        // Django REST Framework validation errors: { field: ["msg", ...], detail: "msg" }
        const d = data as Record<string, unknown>;
        const messages: string[] = [];
        for (const val of Object.values(d)) {
          if (Array.isArray(val)) val.forEach(v => messages.push(String(v)));
          else if (typeof val === 'string') messages.push(val);
        }
        // Show only the first meaningful message (avoid traceback walls of text)
        const display = messages.find(m => m.length < 300) ?? messages[0] ?? 'Failed to save site settings';
        toast.error(display);
      } else {
        toast.error('Failed to save site settings — check backend logs');
      }
    } finally {
      setSavingSite(false);
    }
  };

  type Tab = { id: TabId; label: string; icon: React.ElementType; adminOnly?: boolean };
  const tabs: Tab[] = [
    { id: 'profile',  label: 'Profile',  icon: User },
    { id: 'password', label: 'Password', icon: Lock },
    { id: 'offline',  label: 'Offline',  icon: Database },
    { id: 'site',     label: 'Site',     icon: Settings, adminOnly: true },
  ];

  const visibleTabs = tabs.filter(t => !t.adminOnly || isSuperAdmin);

  return (
    <div className="flex flex-col gap-4 md:gap-6 max-w-2xl page-enter">
      <div>
        <h1 className="page-title">Settings</h1>
        <p className="text-secondary mt-1">Account preferences, offline storage{isSuperAdmin ? ', and site configuration' : ''}.</p>
      </div>

      {/* Account card */}
      <div className="card p-4 flex items-center gap-4">
        <div className="w-12 h-12 md:w-14 md:h-14 rounded-2xl bg-gradient-to-br from-azure-500 to-violet-500 flex items-center justify-center text-base md:text-lg font-display font-bold text-white flex-shrink-0">
          {user?.first_name?.[0]}{user?.last_name?.[0]}
        </div>
        <div>
          <p className="font-display font-bold text-primary">{user?.full_name}</p>
          <p className="text-secondary text-sm">{user?.email}</p>
          <span className="badge badge-blue mt-1">{ROLE_LABELS[user?.role ?? ''] ?? user?.role}</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-800 border border-surface p-1 rounded-xl overflow-x-auto no-scrollbar">
        {visibleTabs.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => { setActiveTab(id); if (id === 'offline') loadOfflineMeta(); }}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs sm:text-sm font-display font-medium transition-all whitespace-nowrap flex-1 justify-center ${
              activeTab === id
                ? 'bg-azure-500 text-white shadow'
                : 'text-secondary hover:text-primary hover:bg-surface-700'
            }`}>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>

      {/* Profile */}
      {activeTab === 'profile' && (
        <div className="card p-5 md:p-6">
          <h2 className="section-title mb-5">Profile Information</h2>
          <form onSubmit={handleProfile(d => profileMutation.mutate(d))} className="flex flex-col gap-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input label="First Name" error={pe.first_name?.message}
                {...regProfile('first_name', { required: 'Required' })} />
              <Input label="Last Name" error={pe.last_name?.message}
                {...regProfile('last_name', { required: 'Required' })} />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="label">Email Address</label>
              <input className="input opacity-50 cursor-not-allowed" value={user?.email ?? ''} disabled readOnly />
              <p className="text-xs text-secondary">Contact an admin to change email.</p>
            </div>
            <Input label="Phone Number" type="tel" placeholder="+255 7XX XXX XXX"
              {...regProfile('phone')} />
            <div className="flex justify-end pt-2">
              <Button type="submit" loading={profileMutation.isPending}>Save Profile</Button>
            </div>
          </form>
        </div>
      )}

      {/* Password */}
      {activeTab === 'password' && (
        <div className="card p-5 md:p-6">
          <h2 className="section-title mb-5">Change Password</h2>
          <form onSubmit={handlePw(d => passwordMutation.mutate(d))} className="flex flex-col gap-4">
            <Input label="Current Password" type="password" error={pwe.old_password?.message}
              {...regPw('old_password', { required: 'Required' })} />
            <Input label="New Password" type="password" error={pwe.new_password?.message}
              {...regPw('new_password', { required: 'Required', minLength: { value: 8, message: 'Min 8 characters' } })} />
            <Input label="Confirm New Password" type="password" error={pwe.confirm_password?.message}
              {...regPw('confirm_password', { required: 'Required', validate: v => v === newPw || 'Passwords do not match' })} />
            <div className="flex justify-end pt-2">
              <Button type="submit" loading={passwordMutation.isPending}>Change Password</Button>
            </div>
          </form>
        </div>
      )}

      {/* Offline / PWA */}
      {activeTab === 'offline' && (
        <div className="flex flex-col gap-4">
          {/* Connection status */}
          <div className={`card p-4 border flex items-center justify-between gap-3 ${
            isOnline ? 'border-emerald-500/20' : 'border-rose-500/20'
          }`}>
            <div className="flex items-center gap-3">
              {isOnline
                ? <Wifi size={18} className="text-emerald-400 flex-shrink-0" />
                : <WifiOff size={18} className="text-rose-400 flex-shrink-0" />}
              <div>
                <p className={`font-display font-semibold text-sm ${isOnline ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {isOnline ? 'Online' : 'Offline'}
                </p>
                <p className="text-xs text-secondary">
                  {lastSynced ? `Last synced: ${lastSynced.toLocaleTimeString('en-TZ')}` : 'Not yet synced this session'}
                </p>
              </div>
            </div>
            {isOnline && (
              <Button variant="secondary" size="sm" onClick={syncNow} loading={isSyncing}>
                <RefreshCw size={13} /> Sync Now
              </Button>
            )}
          </div>

          {/* Pending queue */}
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="section-title">Pending Queue</h2>
              {pendingCount > 0 && (
                <span className="badge badge-amber">{pendingCount} pending</span>
              )}
            </div>
            <p className="text-secondary text-sm mb-3">
              Score entries saved while offline are queued here and synced automatically when you reconnect.
            </p>
            {pendingCount > 0 ? (
              <div className="flex items-center justify-between p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl">
                <p className="text-sm text-amber-400">{pendingCount} score{pendingCount !== 1 ? 's' : ''} waiting to sync</p>
                <Button variant="danger" size="sm" onClick={handleClearPending}>
                  <Trash2 size={13} /> Discard
                </Button>
              </div>
            ) : (
              <p className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-3 py-2">
                ✓ Queue is empty — all changes synced
              </p>
            )}
          </div>

          {/* Cache status */}
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="section-title">Offline Cache</h2>
              {loadingMeta && <RefreshCw size={14} className="text-secondary animate-spin" />}
            </div>
            <p className="text-secondary text-sm mb-3">
              Data cached for offline access. Refreshed automatically every 5 minutes when online.
            </p>
            {syncMeta.length > 0 ? (
              <div className="flex flex-col gap-2 mb-4">
                {syncMeta.map(m => (
                  <div key={m.entity} className="flex items-center justify-between text-xs p-2.5 bg-surface-700 rounded-xl">
                    <span className="font-display font-medium text-primary capitalize">{m.entity}</span>
                    <div className="flex items-center gap-3 text-secondary">
                      <span>{m.record_count} records</span>
                      <span>·</span>
                      <span>{new Date(m.last_synced).toLocaleTimeString('en-TZ')}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-secondary text-xs mb-4">No cache data yet. Go online to populate the cache.</p>
            )}
            <Button variant="danger" size="sm" onClick={handleClearCache}>
              <Trash2 size={13} /> Clear Cache
            </Button>
          </div>

          {/* PWA install info */}
          <div className="card p-4 border-azure-500/20">
            <h2 className="section-title mb-2">Install as App</h2>
            <p className="text-secondary text-sm">
              MathPlatform is installable as a Progressive Web App. On Android, tap{' '}
              <span className="text-primary font-medium">Menu → Add to Home Screen</span>. On iOS, tap{' '}
              <span className="text-primary font-medium">Share → Add to Home Screen</span>.
            </p>
            <p className="text-xs text-secondary mt-2">
              Once installed, the app works fully offline — entering marks, viewing student data, and browsing cached results.
            </p>
          </div>
        </div>
      )}

      {/* Site Settings (Super Admin only) */}
      {activeTab === 'site' && isSuperAdmin && (
        <form onSubmit={siteForm.handleSubmit(handleSaveSiteSettings)} className="flex flex-col gap-4">

          {/* Branding */}
          <div className="card p-5 md:p-6">
            <div className="flex items-center gap-2 mb-5">
              <Globe size={16} className="text-azure-400" />
              <h2 className="section-title">Branding & Identity</h2>
            </div>
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="label flex items-center gap-1.5"><Type size={12} /> Platform Name</label>
                  <input className="input" placeholder="MathPlatform"
                    {...siteForm.register('platform_name', { required: 'Required' })} />
                  {siteForm.formState.errors.platform_name && (
                    <p className="text-xs text-rose-400">{siteForm.formState.errors.platform_name.message}</p>
                  )}
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="label">Subtitle / Region</label>
                  <input className="input" placeholder="Tanzania"
                    {...siteForm.register('platform_subtitle')} />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="label flex items-center gap-1.5"><Hash size={12} /> Logo Letter(s)</label>
                <input className="input max-w-[120px] text-center text-xl font-bold" maxLength={3} placeholder="Σ"
                  {...siteForm.register('logo_letter')} />
                <p className="text-xs text-secondary">1–3 characters shown in the sidebar icon when no logo image is set.</p>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="label flex items-center gap-1.5"><Layout size={12} /> Footer Text</label>
                <input className="input" placeholder="© 2025 MathPlatform · Built for Tanzanian Secondary Schools"
                  {...siteForm.register('footer_text')} />
              </div>
            </div>
          </div>

          {/* Logo */}
          <div className="card p-5 md:p-6">
            <div className="flex items-center gap-2 mb-5">
              <Image size={16} className="text-azure-400" />
              <h2 className="section-title">Logo Image</h2>
            </div>
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <label className="label">Logo URL</label>
                <input
                  className="input"
                  placeholder="https://example.com/logo.png"
                  {...siteForm.register('logo_url', {
                    onChange: e => setLogoPreview(e.target.value),
                  })}
                />
                <p className="text-xs text-secondary">PNG, SVG, or WebP. Displayed in the sidebar header. Leave blank to use logo letter.</p>
              </div>
              {logoPreview && (
                <div className="flex items-center gap-3 p-3 bg-surface-700 rounded-xl border border-surface">
                  <img
                    src={logoPreview}
                    alt="Logo preview"
                    className="h-10 w-10 object-contain rounded-lg"
                    onError={() => setLogoPreview('')}
                  />
                  <p className="text-xs text-secondary">Logo preview</p>
                </div>
              )}
            </div>
          </div>

          {/* Favicon */}
          <div className="card p-5 md:p-6">
            <div className="flex items-center gap-2 mb-5">
              <Monitor size={16} className="text-azure-400" />
              <h2 className="section-title">Favicon</h2>
            </div>
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <label className="label">Favicon URL</label>
                <input
                  className="input"
                  placeholder="https://example.com/favicon.ico"
                  {...siteForm.register('favicon_url', {
                    onChange: e => setFaviconPreview(e.target.value),
                  })}
                />
                <p className="text-xs text-secondary">.ico, .png (32×32 or 64×64), or .svg. Shown in browser tabs and bookmarks.</p>
              </div>
              {faviconPreview && (
                <div className="flex items-center gap-3 p-3 bg-surface-700 rounded-xl border border-surface">
                  <img
                    src={faviconPreview}
                    alt="Favicon preview"
                    className="h-8 w-8 object-contain"
                    onError={() => setFaviconPreview('')}
                  />
                  <div>
                    <p className="text-xs text-primary font-medium">Favicon preview</p>
                    <p className="text-[10px] text-secondary">Appears in browser tab</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Login Page Settings */}
          <div className="card p-5 md:p-6">
            <div className="flex items-center gap-2 mb-5">
              <LogIn size={16} className="text-azure-400" />
              <h2 className="section-title">Login Page</h2>
            </div>
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="label">Tagline</label>
                <input className="input" placeholder="Student Performance Analytics"
                  {...siteForm.register('login_tagline')} />
                <p className="text-xs text-secondary">Shown under the platform name on the login page.</p>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="label">Welcome Heading</label>
                <input className="input" placeholder="Sign in to your account"
                  {...siteForm.register('login_welcome')} />
                <p className="text-xs text-secondary">Heading shown above the login form.</p>
              </div>
              <div className="flex items-center justify-between p-3 bg-surface-700 rounded-xl border border-surface">
                <div>
                  <p className="text-sm font-display font-medium text-primary">Background Glow</p>
                  <p className="text-xs text-secondary">Show ambient azure glow effect on login background.</p>
                </div>
                <button
                  type="button"
                  onClick={() => siteForm.setValue('login_bg_gradient', !siteForm.watch('login_bg_gradient'))}
                  className={`w-11 h-6 rounded-full transition-colors relative flex-shrink-0 ${
                    siteForm.watch('login_bg_gradient') ? 'bg-azure-500' : 'bg-surface-600'
                  }`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                    siteForm.watch('login_bg_gradient') ? 'translate-x-5' : 'translate-x-0'
                  }`} />
                </button>
              </div>
            </div>
          </div>

          {/* Page Settings */}
          <div className="card p-5 md:p-6">
            <div className="flex items-center gap-2 mb-2">
              <Layout size={16} className="text-azure-400" />
              <h2 className="section-title">Page Settings</h2>
            </div>
            <p className="text-secondary text-sm mb-5">Configure pagination and visibility for each page.</p>
            <div className="flex flex-col gap-3">
              {PAGE_REGISTRY.map(({ key, label, description }) => (
                <div key={key} className="flex items-center justify-between gap-3 p-3 bg-surface-700 rounded-xl border border-surface">
                  <div className="flex items-center gap-2 min-w-0">
                    <button
                      type="button"
                      onClick={() => setPageEnabled(prev => ({ ...prev, [key]: !prev[key] }))}
                      className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                        pageEnabled[key] !== false
                          ? 'bg-azure-500/20 text-azure-400'
                          : 'bg-surface-600 text-secondary'
                      }`}
                      title={pageEnabled[key] !== false ? 'Visible' : 'Hidden'}
                    >
                      {pageEnabled[key] !== false ? <Eye size={13} /> : <EyeOff size={13} />}
                    </button>
                    <div className="min-w-0">
                      <p className="text-sm font-display font-medium text-primary">{label}</p>
                      <p className="text-[11px] text-secondary truncate">{description}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <label className="text-[11px] text-secondary whitespace-nowrap flex items-center gap-1">
                      <Hash size={10} /> Per page
                    </label>
                    <select
                      className="input py-1 text-xs w-16"
                      value={pageSizes[key] ?? 20}
                      onChange={e => setPageSizes(prev => ({ ...prev, [key]: Number(e.target.value) }))}
                    >
                      {PAGE_SIZE_OPTIONS.map(n => (
                        <option key={n} value={n}>{n}</option>
                      ))}
                    </select>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end">
            <Button type="submit" loading={savingSite}>
              <Save size={14} /> Save Site Settings
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
