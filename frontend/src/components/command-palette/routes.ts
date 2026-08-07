// Every reachable static (non-parametrized) route in App.tsx, with
// display labels and search keywords for the `goto` command's fuzzy
// matching. Keep this in sync with App.tsx's <Routes> — it's the thing
// that makes the palette able to reach "every corner of the site".
export interface RouteEntry {
  path: string;
  label: string;
  keywords: string[];
  adminOnly?: boolean;
}

export const ROUTES: RouteEntry[] = [
  { path: '/dashboard', label: 'Dashboard', keywords: ['home', 'overview'] },
  { path: '/students', label: 'Students', keywords: ['student', 'list', 'roster'] },
  { path: '/students/new', label: 'Add Student', keywords: ['create', 'new', 'enroll'] },
  { path: '/classrooms', label: 'Classrooms', keywords: ['class', 'classes'] },
  { path: '/classrooms/new', label: 'Add Classroom', keywords: ['create', 'new'] },
  { path: '/exams', label: 'Exams', keywords: ['exam', 'test', 'assessment'] },
  { path: '/exams/pending-review', label: 'Exams — Pending Review', keywords: ['review', 'approve'] },
  { path: '/exams/trash', label: 'Exams — Trash', keywords: ['deleted', 'recover', 'restore'], adminOnly: true },
  { path: '/exams/new', label: 'Create Exam', keywords: ['new'] },
  { path: '/import', label: 'Bulk Import', keywords: ['import', 'marks', 'upload', 'csv'] },
  { path: '/groups', label: 'Peer Groups', keywords: ['group', 'peer', 'pairing'] },
  { path: '/analytics', label: 'Analytics', keywords: ['dashboard', 'stats'] },
  { path: '/analytics/class', label: 'Analytics — Class', keywords: ['classroom'] },
  { path: '/analytics/compare', label: 'Analytics — Compare Streams', keywords: ['stream', 'comparison'] },
  { path: '/analytics/risk', label: 'Analytics — Risk Scores', keywords: ['risk'] },
  { path: '/analytics/dependencies', label: 'Analytics — Topic Dependencies', keywords: ['topic', 'chain'] },
  { path: '/analytics/integrity', label: 'Analytics — Integrity', keywords: ['flags', 'cheating', 'audit'] },
  { path: '/analytics/teacher-consistency', label: 'Analytics — Teacher Consistency', keywords: ['grading'], adminOnly: true },
  { path: '/at-risk', label: 'At-Risk Students', keywords: ['risk', 'flagged'] },
  { path: '/notifications', label: 'Notifications', keywords: ['inbox', 'alerts'] },
  { path: '/settings/notifications', label: 'Notification Settings', keywords: ['preferences', 'email'] },
  { path: '/reports', label: 'Reports', keywords: ['report', 'export', 'pdf'] },
  { path: '/users', label: 'Users', keywords: ['user', 'accounts', 'staff'] },
  { path: '/settings', label: 'Settings', keywords: ['config', 'preferences'] },
  { path: '/grade-levels', label: 'Grade Levels', keywords: ['grade'], adminOnly: true },
  { path: '/subjects', label: 'Subjects', keywords: ['subject'], adminOnly: true },
  { path: '/audit-log', label: 'Audit Log', keywords: ['log', 'history', 'trail'], adminOnly: true },
];
