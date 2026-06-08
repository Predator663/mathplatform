import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface PageConfig {
  enabled: boolean;
  page_size: number;
  label?: string;
}

export interface SiteSettings {
  platform_name: string;
  platform_subtitle: string;
  logo_url: string;
  logo_letter: string;
  favicon_url: string;
  footer_text: string;
  login_tagline: string;
  login_welcome: string;
  login_bg_gradient: boolean;
  page_settings: Record<string, PageConfig>;
}

const DEFAULTS: SiteSettings = {
  platform_name: 'MathPlatform',
  platform_subtitle: 'Tanzania',
  logo_url: '',
  logo_letter: 'Σ',
  favicon_url: '',
  footer_text: '© 2025 MathPlatform · Built for Tanzanian Secondary Schools',
  login_tagline: 'Student Performance Analytics',
  login_welcome: 'Sign in to your account',
  login_bg_gradient: true,
  page_settings: {},
};

// Page registry — all pages that have controls
export const PAGE_REGISTRY: { key: string; label: string; description: string }[] = [
  { key: 'students',   label: 'Students',         description: 'Student list & profiles' },
  { key: 'exams',      label: 'Exams',             description: 'Exam list & details' },
  { key: 'classrooms', label: 'Classrooms',        description: 'Classroom management' },
  { key: 'users',      label: 'Users',             description: 'User management (admin)' },
  { key: 'analytics',  label: 'Analytics',         description: 'Analytics overview' },
  { key: 'at_risk',    label: 'At-Risk Students',  description: 'At-risk student tracking' },
  { key: 'reports',    label: 'Reports',           description: 'Report generation' },
  { key: 'dashboard',  label: 'Dashboard',         description: 'Main dashboard' },
  { key: 'marks',      label: 'Mark Entry',        description: 'Exam mark entry' },
  { key: 'import',     label: 'Bulk Import',       description: 'Bulk data import' },
];

interface SiteSettingsState {
  settings: SiteSettings;
  loaded: boolean;
  setSettings: (s: SiteSettings) => void;
  getPage: (key: string) => PageConfig;
}

export const useSiteSettingsStore = create<SiteSettingsState>()(
  persist(
    (set, get) => ({
      settings: DEFAULTS,
      loaded: false,
      setSettings: (settings) => set({ settings, loaded: true }),
      getPage: (key) => ({
        ...get().settings.page_settings[key],
        enabled: get().settings.page_settings[key]?.enabled ?? true,
        page_size: get().settings.page_settings[key]?.page_size ?? 20,
      }),
    }),
    { name: 'site-settings' }
  )
);
