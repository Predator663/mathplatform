import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface PageConfig {
  enabled: boolean;
  page_size: number;
  label?: string;
}

export type TeacherResource = 'students' | 'exams' | 'classrooms' | 'subjects';
export type TeacherAction = 'add' | 'edit' | 'delete';
export type TeacherPermissionsMap = Record<TeacherResource, Record<TeacherAction, boolean>>;

export interface SiteSettings {
  platform_name: string;
  platform_subtitle: string;
  logo_url: string;
  logo_letter: string;
  favicon_url: string;
  pwa_icon_url: string;
  footer_text: string;
  login_tagline: string;
  login_welcome: string;
  login_bg_gradient: boolean;
  page_settings: Record<string, PageConfig>;
  privacy_policy: string;
  terms_of_use: string;
  about_me: string;
  // Admin overrides only (may be a partial/empty object) — use
  // teacher_permissions_resolved for the always-complete merged view.
  teacher_permissions: Partial<TeacherPermissionsMap>;
  // Server-computed: defaults merged with teacher_permissions overrides.
  // Always has every resource/action key present.
  teacher_permissions_resolved: TeacherPermissionsMap;
}

// Mirrors backend DEFAULT_TEACHER_PERMISSIONS (accounts/models.py) so the UI
// has sane fallbacks before the first successful settings fetch.
export const DEFAULT_TEACHER_PERMISSIONS: TeacherPermissionsMap = {
  students:   { add: true,  edit: true,  delete: true },
  exams:      { add: true,  edit: true,  delete: true },
  classrooms: { add: true,  edit: true,  delete: true },
  subjects:   { add: false, edit: false, delete: false },
};

const DEFAULTS: SiteSettings = {
  platform_name: 'MathPlatform',
  platform_subtitle: 'Tanzania',
  logo_url: '',
  logo_letter: 'Σ',
  favicon_url: '',
  pwa_icon_url: '',
  footer_text: '© 2025 MathPlatform · Built for Tanzanian Secondary Schools',
  login_tagline: 'Student Performance Analytics',
  login_welcome: 'Sign in to your account',
  login_bg_gradient: true,
  page_settings: {},
  privacy_policy: '',
  terms_of_use: '',
  about_me: '',
  teacher_permissions: {},
  teacher_permissions_resolved: DEFAULT_TEACHER_PERMISSIONS,
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
  /** Whether a teacher may perform `action` on `resource`, per the
   * admin-configured toggles. Only meaningful for role === 'teacher';
   * callers should let super_admin through unconditionally themselves. */
  canTeacher: (resource: TeacherResource, action: TeacherAction) => boolean;
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
      canTeacher: (resource, action) => {
        const resolved = get().settings.teacher_permissions_resolved;
        return resolved?.[resource]?.[action] ?? DEFAULT_TEACHER_PERMISSIONS[resource][action];
      },
    }),
    { name: 'site-settings' }
  )
);
