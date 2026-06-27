# Changelog — Offline, Assignment & Dashboard Fixes

## Critical fixes

1. **Pagination silently capped every list at 20 items** (`backend/mathapi/settings/base.py`,
   new `backend/mathapi/core/pagination.py`)
   DRF's pagination never had `page_size_query_param` set, so every
   `?page_size=500` the frontend sent (offline sync, report pickers, bulk
   import) was ignored and silently truncated to 20 rows. This was the root
   cause of the offline feature only ever caching a fraction of students/
   exams/classrooms in any school with >20 records. Added
   `LargePageNumberPagination` (page_size_query_param='page_size',
   max_page_size=1000) as the new default.

2. **Teacher assignment was completely non-functional**
   - `ClassroomSerializer` never exposed a `teachers` field, so the
     "Assign Teacher" dropdown on Create Classroom silently did nothing.
   - `get_teacher_classrooms(user, base_qs=qs)` was called with a `base_qs`
     kwarg the function didn't accept — a hard `TypeError` crash for any
     teacher loading their classrooms list.
   - There was no UI anywhere to create a `TeacherAssignment` (the real,
     working mechanism), and no classroom detail route at all even though
     classroom cards linked to one.
   - **Fix:** added `base_qs` support to `get_teacher_classrooms`; removed
     the dead dropdown from Create Classroom; built a new
     `ClassroomDetailPage` (`/classrooms/:id`) with a full assign/remove
     teacher-assignment UI, gated to admins.

3. **Exam publish status went stale in the list view**
   Publishing an exam invalidated only the single-exam query, not the
   exams list, so `ExamsPage` kept showing "Draft" after publishing.
   Added the missing invalidation, plus a new `unpublish` action (backend
   + frontend) since there was previously no way to undo a publish.

4. **Subject color/icon picker was broken**
   `SubjectsPage` called `reset(fn)` to update color/icon presets — react-
   hook-form's `reset()` doesn't support a functional updater like
   `useState` does. Switched to `setValue()`, and added a visible
   "selected" state on the active swatch/icon.

5. **Offline reads didn't exist** — only writes (score queueing) worked
   offline; opening Mark Entry/Exams/Classrooms while offline showed
   blank/"not found" because cached IndexedDB data was written but never
   read back. Added `useOfflineData.ts` with hooks that fall back to the
   IndexedDB snapshot when the network request fails, wired into
   `MarkEntryPage`, `ExamsPage`, and `ClassroomsPage`, each with a visible
   "showing data saved on this device" badge.

6. **Dashboard vs At-Risk page disagreed on the same number**
   The dashboard always used the at-risk service's default threshold
   (50%) while the At-Risk page defaulted its selector to 30%. Aligned
   the dashboard to 30% (Tanzania O-Level pass mark) so both agree unless
   a user explicitly changes the At-Risk page's filter.

## New dashboard graphs (all backed by real ORM aggregates, not placeholders)

- Fixed the existing "Recent Exams" chart, which was plotting a fake
  1-2-3 sequence number instead of any real score — it now shows actual
  average % per exam, with pass rate in the tooltip.
- Added a **Grade Distribution** bar chart (A/B/C/D/F counts) using the
  same unified grading thresholds (A≥75, B 65–74, C 45–64, D 30–44, F<30)
  applied everywhere else in the app.
- Added a **Classroom Comparison** bar chart showing average % per
  classroom (up to 12), with student count in the tooltip.
- All three are computed server-side in `DashboardSummaryView` via direct
  ORM queries (bypassing the pagination bug entirely) and respect the
  same teacher/admin scoping and optional subject filter as the rest of
  the dashboard.

## Files touched

**Backend:** `analytics/views.py`, `accounts/scoping.py`, `exams/views.py`,
`settings/base.py`, new `core/pagination.py`

**Frontend:** `pages/classrooms/{CreateClassroomPage,ClassroomsPage}.tsx`,
new `pages/classrooms/ClassroomDetailPage.tsx`, `pages/exams/{ExamsPage,
ExamDetailPage}.tsx`, `pages/subjects/SubjectsPage.tsx`,
`pages/marks/MarkEntryPage.tsx`, `pages/dashboard/DashboardPage.tsx`,
new `hooks/useOfflineData.ts`, `App.tsx`, `api/index.ts`, `types/index.ts`
