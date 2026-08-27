export type NotificationFrequency = 'immediate' | 'digest' | 'off';

export interface NotificationPreferenceItem {
  category: string; category_label: string;
  frequency: NotificationFrequency; is_default: boolean;
}

export interface NotificationLogEntry {
  id: number; category: string; category_label: string;
  subject: string; summary: string;
  related_object_type: string; related_object_id: number | null;
  status: 'sent' | 'failed' | 'skipped';
  sent_at: string; read_at: string | null;
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export type UserRole = 'super_admin' | 'teacher' | 'student' | 'parent';

export interface User {
  id: number; email: string; first_name: string; last_name: string;
  full_name: string; role: UserRole; is_active: boolean;
  date_joined: string; phone: string; avatar: string | null;
  // Only set when role === 'student' — the linked StudentProfile's id,
  // needed to call the id-based analytics endpoints for "my own" data.
  student_profile_id?: number | null;
}

export interface AuthTokens { access: string; refresh: string; }
export interface LoginResponse extends AuthTokens { user: User; }

// ── Subjects & Assignments ────────────────────────────────────────────────────
export interface Subject {
  id: number; name: string; code: string; color: string; icon: string;
  is_active: boolean; teacher_count?: number; exam_count?: number;
}

export interface TeacherAssignment {
  id: number;
  teacher: number; teacher_name: string; teacher_email: string;
  classroom: number; classroom_name: string;
  subject: number; subject_name: string; subject_code: string; subject_color: string;
  created_at: string;
}

// ── AuditLog ──────────────────────────────────────────────────────────────────
export type AuditAction = 'create' | 'update' | 'delete' | 'login' | 'logout';
export interface AuditLogFieldChange { old: unknown; new: unknown }

export interface AuditLog {
  id: number; user: number; user_name: string; user_email: string;
  action: AuditAction; action_display: string;
  model_name: string; object_id: string;
  description: string; changes: Record<string, AuditLogFieldChange> | null;
  ip_address: string | null; timestamp: string;
}

export interface AuditLogFacets {
  actions: { value: AuditAction; label: string }[];
  models: string[];
  users: { id: number; email: string; name: string }[];
}

export interface AuditLogStats {
  total: number;
  by_action: Record<AuditAction, number>;
  top_models: { model_name: string; count: number }[];
  top_users: { id: number; email: string; name: string; count: number }[];
}

// ── Tanzania Curriculum ───────────────────────────────────────────────────────
export type EducationLevel = 'pre_primary' | 'primary' | 'o_level' | 'a_level' | 'technical';
export type ClassStream = 'general' | 'science' | 'arts' | 'commerce' | 'technical';

export interface GradeLevel {
  id: number; name: string; short_name: string;
  education_level: EducationLevel; education_level_display: string;
  order: number; necta_exam: string; math_subject: string;
}

export interface ClassroomTeacherAssignment {
  teacher_id: number; teacher_name: string;
  subject_id: number; subject_name: string; subject_code: string;
}

export interface Stream {
  id: number; classroom: number; classroom_name?: string;
  name: string; capacity: number | null; is_active: boolean;
  student_count: number; created_at: string;
}

export interface StreamComparisonRow {
  stream_id: number | null; stream_name: string;
  student_count: number; exams_recorded: number;
  average: number | null; pass_rate: number | null;
  highest: number | null; lowest: number | null;
  std_dev: number | null; at_risk_count: number;
}

export interface StreamComparison {
  classroom_id: number; classroom_name: string;
  streams: StreamComparisonRow[];
}

export interface Classroom {
  id: number; name: string;
  grade_level: number; grade_level_name: string; grade_level_short: string;
  education_level: EducationLevel; education_level_display: string;
  stream: ClassStream; stream_display: string;
  academic_year: string; teacher_names: string[];
  teacher_assignments: ClassroomTeacherAssignment[];
  is_active: boolean; student_count: number;
  necta_exam: string; math_subject: string; created_at: string;
  streams: Stream[];
}

// ── Peer Groups ───────────────────────────────────────────────────────────
export type PerformanceTier = 'very_strong' | 'strong' | 'average' | 'weak' | 'unrated';

export interface StudentPerformanceRow {
  student_id: number; student_name: string; student_code: string;
  average: number | null; exams_taken: number; tier: PerformanceTier;
  stream_id: number | null; stream_name: string | null;
}

export interface GroupMember {
  id: number; student_id: number; student_name: string; student_code: string;
  student_stream_id: number | null; student_stream_name: string | null;
  tier: PerformanceTier; tier_display: string;
  average_at_placement: number | null; is_anchor: boolean; joined_at: string;
}

export interface StudentGroup {
  id: number; classroom: number; classroom_name: string;
  name: string; academic_year: string;
  subject: number | null; subject_name: string | null;
  stream: number | null; stream_name: string | null;
  term: string; description: string;
  badge_image_url: string | null; badge_color: string;
  created_by: number | null; created_at: string; updated_at: string;
  members: GroupMember[]; member_count: number; group_average: number | null;
}

export interface GroupsOverview {
  classroom_id: number; classroom_name: string; academic_year: string;
  performance: StudentPerformanceRow[];
  tier_counts: Record<PerformanceTier, number>;
  groups: StudentGroup[];
  ungrouped_students: StudentPerformanceRow[];
}

export interface GroupTransferLogEntry {
  id: number; student: number; student_name: string;
  from_group: number | null; from_group_name: string | null;
  to_group: number | null; to_group_name: string | null;
  reason: string; warnings: string;
  transferred_by: number | null; transferred_by_name: string | null;
  transferred_at: string;
}

export interface GroupEffectivenessMember {
  student_id: number; student_name: string;
  tier_at_placement: PerformanceTier; average_at_placement: number | null;
  current_average_since_joining: number | null; exams_since_joining: number;
  delta: number | null; is_anchor: boolean;
}

export interface GroupEffectivenessRow {
  group_id: number; group_name: string; member_count: number;
  members: GroupEffectivenessMember[];
  average_delta: number | null; has_sufficient_data: boolean;
}

export interface GroupEffectivenessOverview {
  classroom_id: number; classroom_name: string; academic_year: string;
  groups: GroupEffectivenessRow[];
  classroom_average_delta: number | null;
  anchor_average_delta: number | null;
  non_anchor_average_delta: number | null;
  students_with_data: number;
}

export interface TierChangeEntry {
  student_id: number; student_name: string; group_id: number; group_name: string;
  tier_at_placement: PerformanceTier; current_tier: PerformanceTier;
  current_average: number | null; direction: 'up' | 'down'; magnitude: number;
}

export interface RebalanceCandidate {
  student_id: number; student_name: string;
  from_group_id: number; from_group_name: string;
  current_tier: PerformanceTier; current_average: number | null;
}

export interface GroupNeedingAttention {
  group_id: number; group_name: string; reason: string; candidates: RebalanceCandidate[];
}

export interface RebalanceSuggestions {
  classroom_id: number; classroom_name: string; academic_year: string;
  tier_changes: TierChangeEntry[];
  groups_needing_attention: GroupNeedingAttention[];
}

// ── Group Assignments (marks + analytics) ───────────────────────────────────
export type AssignmentType = 'classwork' | 'homework' | 'project' | 'practical' | 'presentation' | 'other';

export interface GroupAssignment {
  id: number; classroom: number; classroom_name: string;
  stream: number | null; stream_name: string | null;
  subject: number | null; subject_name: string | null;
  title: string; description: string;
  assignment_type: AssignmentType; assignment_type_display: string;
  term: string; term_display: string | null; academic_year: string;
  date_given: string; due_date: string | null; max_score: number;
  created_by: number | null; created_at: string; updated_at: string;
  groups_scored: number; groups_expected: number;
}

export interface GroupAssignmentMemberMark {
  id: number; student_id: number; student_name: string; student_code: string;
  adjustment: number; is_excused: boolean; note: string;
  effective_score: number; percentage: number; updated_at: string;
}

export interface GroupAssignmentScore {
  id: number; assignment: number; group: number; group_name: string;
  stream_id: number | null; stream_name: string | null;
  score: number; percentage: number; is_absent: boolean; remarks: string;
  member_marks: GroupAssignmentMemberMark[];
  entered_by: number | null; entered_by_name: string | null;
  entered_at: string; updated_at: string;
}

export interface GroupAssignmentRosterRow {
  group_id: number; group_name: string; stream_id: number | null; stream_name: string | null;
  member_count: number;
  members: { student_id: number; student_name: string }[];
  score: GroupAssignmentScore | null;
}

export interface GroupAssignmentRoster {
  assignment: GroupAssignment;
  groups: GroupAssignmentRosterRow[];
}

export interface GroupWorkTrendPoint {
  assignment_id: number; title: string; date: string;
  assignment_type: AssignmentType; average_pct: number; groups_scored: number;
}

export interface GroupWorkPerGroup {
  group_id: number; group_name: string; stream_id: number | null; stream_name: string | null;
  assignments_count: number; average_pct: number; best_pct: number; worst_pct: number;
  trend: { assignment_id: number; title: string; date: string; pct: number }[];
}

export interface GroupWorkPerStream {
  stream_id: number | null; stream_name: string;
  group_count: number; assignments_scored: number; average_pct: number;
}

export interface GroupWorkAnalytics {
  classroom_id: number; classroom_name: string;
  classroom_average_pct: number | null;
  assignments_count: number; groups_scored_count: number;
  distribution: Record<string, number>;
  trend: GroupWorkTrendPoint[];
  per_group: GroupWorkPerGroup[];
  per_stream: GroupWorkPerStream[];
  top_groups: GroupWorkPerGroup[];
  bottom_groups: GroupWorkPerGroup[];
}

export interface GroupWorkReassignCandidate {
  student_id: number; student_name: string;
  from_group_id: number; from_group_name: string;
  current_tier: PerformanceTier; individual_average: number | null;
}

export interface GroupWorkGroupStatus {
  group_id: number; group_name: string; stream_id: number | null; stream_name: string | null;
  average_pct: number; assignments_count: number;
  status: 'below_average' | 'average' | 'above_average';
}

export interface GroupWorkUnderperforming {
  group_id: number; group_name: string; stream_id: number | null; stream_name: string | null;
  average_pct: number; gap_from_classroom_average: number;
  candidates: GroupWorkReassignCandidate[];
}

export interface GroupWorkReassignmentSuggestions {
  classroom_id: number; classroom_name: string;
  classroom_average_pct: number | null;
  groups: GroupWorkGroupStatus[];
  underperforming: GroupWorkUnderperforming[];
}

export type PeerConstraintType = 'avoid' | 'prefer';

export interface PeerConstraintEntry {
  id: number; classroom: number;
  student_a: number; student_a_name: string;
  student_b: number; student_b_name: string;
  constraint_type: PeerConstraintType; constraint_type_display: string;
  reason: string; created_by: number | null; created_at: string;
}

export interface StudentProfile {
  id: number; student_id: string; full_name: string;
  first_name: string; last_name: string; email: string;
  classroom: number | null; classroom_name: string | null;
  stream: number | null; stream_name: string | null;
  grade_level: string | null; education_level: EducationLevel | null;
  date_of_birth: string | null; enrollment_date: string; is_active: boolean;
  notes: string; index_number: string; parent_name: string;
  parent_phone: string; district: string; region: string;
  target_percentage: number | null;
}

export type DuplicateMatchField = 'name' | 'email' | 'index_number' | 'parent_phone' | 'date_of_birth';

export interface DuplicateGroup {
  key: string; count: number; students: StudentProfile[];
}

// ── Exams ─────────────────────────────────────────────────────────────────────
export type ExamType =
  | 'monthly_test' | 'mid_term' | 'terminal' | 'mock'
  | 'necta' | 'psle' | 'csee' | 'acsee' | 'diagnostic';

export type TermType = 'term_1' | 'term_2' | 'term_3' | 'annual';

export interface MathTopic {
  id: number; name: string; description: string;
  color: string; order: number; is_active: boolean;
  subject: number | null; subject_name: string | null;
  subject_code: string | null; subject_color: string | null;
  grade_level: number | null; grade_level_name: string | null;
  grade_level_short: string | null;
}

export interface ExamTopicWeight {
  id: number; topic: number; topic_name: string;
  topic_color: string; max_marks: number; weight_percentage: number;
}

export interface Exam {
  id: number; title: string; exam_type: ExamType; term: TermType;
  academic_year: string; exam_date: string; max_score: number;
  passing_score: number; passing_percentage: number;
  classrooms: number[]; topic_weights: ExamTopicWeight[];
  created_by: number; created_by_name: string; description: string;
  is_published: boolean; created_at: string; updated_at: string;
  score_count: number; average_score: number | null; pass_rate: number | null;
  subject: number | null; subject_name: string | null;
  subject_code: string | null; subject_color: string | null;
}

export interface TopicScore {
  id: number; topic: number; topic_name: string; topic_color: string;
  score: number; max_marks: number; percentage: number;
}

export interface ExamScore {
  id: number; exam: number; exam_title: string; exam_date: string;
  exam_type: ExamType; max_score: number; student: number;
  student_name: string; student_id_code: string; score: number;
  percentage: number; passed: boolean; letter_grade: string;
  is_absent: boolean; remarks: string; topic_scores: TopicScore[];
  entered_by: number; entered_at: string; updated_at: string;
}

// ── Student Comparison ───────────────────────────────────────────────────
export interface ComparisonTimelinePoint {
  exam_id: number; exam_title: string; exam_type: ExamType; term: TermType;
  academic_year: string; exam_date: string; score: number; max_score: number;
  percentage: number; letter_grade: string; passed: boolean;
}

export interface ComparisonTopic {
  topic_id: number; topic_name: string; color: string;
  average: number; highest: number; lowest: number; attempts: number;
  trend: 'improving' | 'declining' | 'stable';
  history: { percentage: number; exam_date: string; exam_title: string }[];
}

export interface ComparisonGrowth {
  first_pct: number | null; last_pct: number | null; delta: number | null;
}

export interface StudentComparisonProfile {
  student_id: number; name: string; student_code: string; classroom: string | null;
  summary: {
    total_exams: number; average_percentage: number | null;
    highest_percentage: number; lowest_percentage: number;
    pass_rate: number; trend: string; predicted_necta_grade: string | null;
  };
  timeline: ComparisonTimelinePoint[];
  trend: 'improving' | 'declining' | 'stable';
  moving_average: number[];
  topics: ComparisonTopic[];
  growth: ComparisonGrowth;
  quiz_streak: number | null;
  badge_count: number | null;
}

export interface StudentComparisonResult {
  students: StudentComparisonProfile[];
  missing_ids: number[];
}

// ── Daily Quizzes ─────────────────────────────────────────────────────────
export interface DailyQuiz {
  id: number; date: string; classroom: number; classroom_name: string;
  subject: number; subject_name: string; subject_color: string;
  topic: number | null; topic_name: string | null;
  title: string; display_title: string;
  term: TermType; academic_year: string;
  max_score: number; passing_score: number; passing_percentage: number;
  notes: string; created_by: number | null; created_by_name: string | null;
  created_at: string; updated_at: string;
  score_count: number; average_score: number | null; pass_rate: number | null;
}

export interface DailyQuizScore {
  id: number; quiz: number; quiz_title: string; quiz_date: string; max_score: number;
  student: number; student_name: string; student_id_code: string;
  score: number; percentage: number; passed: boolean; letter_grade: string;
  is_absent: boolean; remarks: string;
  entered_by: number | null; entered_at: string; updated_at: string;
}

export interface QuizAnalyticsOverview {
  quiz_count: number; scores_entered: number; present_count: number; absent_count: number;
  average_score: number | null; pass_rate: number | null; participation_rate: number | null;
}

export interface QuizTrendPoint {
  date: string; average: number; pass_rate: number; quiz_count: number;
}

export interface QuizTopicBreakdown {
  topic_id: number | null; topic_name: string;
  attempts: number; average: number; highest: number; lowest: number;
  trend: 'improving' | 'declining' | 'stable';
}

export interface QuizStudentAverage {
  student_id: number; student_name: string; average: number; attempts: number;
}

export interface ClassroomQuizAnalytics {
  overview: QuizAnalyticsOverview;
  trend: QuizTrendPoint[];
  topic_breakdown: QuizTopicBreakdown[];
  at_risk_students: QuizStudentAverage[];
  top_students: QuizStudentAverage[];
}

export interface QuizStreak {
  current_streak: number; longest_streak: number;
  last_quiz_date: string | null; updated_at: string;
}

export interface QuizProgressTimelinePoint {
  exam_date: string; percentage: number; exam_title: string; exam_id: number;
}

export interface StudentQuizProgress {
  student_id?: number;
  summary: {
    quizzes_taken: number; quizzes_absent: number;
    average: number | null; pass_rate: number | null;
    highest: number | null; lowest: number | null;
    trend: 'improving' | 'declining' | 'stable';
    best_topic: string | null; weakest_topic: string | null;
  };
  timeline: QuizProgressTimelinePoint[];
  moving_average: number[];
  topic_data: QuizTopicBreakdown[];
  streak: QuizStreak;
  badges: StudentBadgeAward[];
}


export interface ParentStudentLink {
  id: number; parent: number; parent_name: string;
  student: number; student_name: string;
  relationship: string; is_primary: boolean; created_at: string;
}

export interface StudentSummary {
  student_id: number; student_name: string; student_code: string;
  classroom: string | null; total_exams: number;
  average_percentage: number | null; highest_percentage: number;
  lowest_percentage: number; pass_rate: number;
  trend: 'improving' | 'stable' | 'declining' | 'no_data';
  predicted_necta_grade: string | null;
  recent_scores: RecentScore[];
}

export interface RecentScore {
  exam_id: number; exam_title: string; exam_type: ExamType;
  exam_date: string; score: number; max_score: number;
  percentage: number; letter_grade: string; passed: boolean;
}

export interface TrendDataPoint {
  exam_id: number; exam_title: string; exam_type: ExamType; term: TermType;
  academic_year: string; exam_date: string; score: number; max_score: number;
  percentage: number; letter_grade: string; passed: boolean;
}

export interface StudentTrend {
  student_id: number; timeline: TrendDataPoint[];
  trend: 'improving' | 'stable' | 'declining' | 'no_data';
  trend_slope: number; moving_average: number[];
}

export interface TopicAnalysis {
  topic_id: number; topic_name: string; color: string;
  average: number; highest: number; lowest: number;
  attempts: number; trend: 'improving' | 'stable' | 'declining';
  history: { percentage: number; exam_date: string; exam_title: string }[];
}

export interface StudentTopicAnalysis { student_id: number; topics: TopicAnalysis[]; }

export interface StudentClassroomComparison {
  by_exam: Record<string, number>; // exam_id -> classroom average %
  rank: number | null;
  class_size: number;
  percentile: number | null;
}

export interface ExamSummary {
  exam_id: number; exam_title: string; exam_type: ExamType; term: TermType;
  exam_date: string; subject: string | null; student_count: number; average: number;
  highest: number; lowest: number; pass_rate: number; std_dev: number;
}

export interface StudentRanking {
  student_id: number; student_name: string; student_code: string;
  average: number; exams_taken: number; rank: number;
}

export interface WeakTopic { topic: string; avg: number; subject: string | null; }

export interface ClassAnalytics {
  classroom_id: number; classroom_name: string; grade_level: string;
  exam_summaries: ExamSummary[]; overall_average: number | null;
  student_rankings: StudentRanking[]; at_risk_students: StudentRanking[];
  top_performers: StudentRanking[]; distribution: Record<string, number>;
  weak_topics: WeakTopic[]; weak_topic_count: number;
}

// ── Topic Heatmap ───────────────────────────────────────────────────────────
export interface HeatmapTopic { id: number; name: string; color: string; }
export interface HeatmapStudent { id: number; name: string; code: string; }
export interface HeatmapRow {
  student: HeatmapStudent;
  /** Keyed by topic id (as string, since it travels through JSON). Null = no data yet. */
  topics: Record<string, number | null>;
}
export interface TopicHeatmap {
  classroom_id: number; topics: HeatmapTopic[]; rows: HeatmapRow[];
}

export interface ComparisonClassroom {
  classroom_id: number; classroom_name: string;
  overall_average: number | null; exam_summaries: ExamSummary[];
}
export interface ComparativeAnalysis { comparisons: ComparisonClassroom[]; }

export interface AtRiskStudent {
  student_id: number; student_name: string; student_code: string;
  classroom: string | null; recent_average: number; recent_scores: number[];
  flags: { below_threshold: boolean; declining: boolean };
}

export interface MostImprovedStudent {
  student_id: number; student_name: string; student_code: string;
  classroom: string | null;
  first_percentage: number; latest_percentage: number;
  delta: number; exams_counted: number;
}

// ── Intelligence layer ──────────────────────────────────────────────────────

export interface IntegrityEditEntry {
  edit_id: number; student_name: string; exam_title: string; exam_date: string;
  changed_by: string; old_score: number; new_score: number;
  old_percentage: number; new_percentage: number; delta: number;
  reason: string; changed_at: string;
}
export interface IntegrityEditorRate {
  teacher_id: number; teacher_name: string; edits_made: number;
  scores_entered: number; edit_rate_percent: number | null;
}
export interface IntegrityFlags {
  boundary_crossings: IntegrityEditEntry[]; boundary_crossing_count: number;
  large_jumps: IntegrityEditEntry[]; large_jump_count: number;
  editor_rates: IntegrityEditorRate[];
}

export type RiskLevel = 'critical' | 'high' | 'moderate' | 'low' | 'insufficient_data';
export interface RiskFactors {
  trend_contribution: number; volatility_contribution: number;
  topic_gap_contribution: number | null; pass_margin_contribution: number;
  recent_average: number; recent_trend_slope: number; volatility: number;
  weakest_topics_avg: number | null;
}
export interface StudentRiskScore {
  student_id: number; student_name?: string;
  risk_score: number | null; risk_level: RiskLevel; factors: Partial<RiskFactors>;
}
export interface ClassroomRiskScores {
  classroom_id: number; students: StudentRiskScore[];
}

export interface TopicDependencyChain {
  from_topic: string; to_topic: string;
  baseline_weak_rate: number; conditional_weak_rate: number;
  lift: number; sample_size: number;
}
export interface TopicDependencyChains {
  classroom_id: number | null; dependency_chains: TopicDependencyChain[];
}

export interface TeacherConsistencyFlag {
  topic: string; teacher_id: number; teacher_name: string;
  teacher_average: number; peer_average: number; z_score: number;
  direction: 'lenient' | 'harsh'; sample_size: number;
}
export interface TeacherGradingConsistency {
  flags: TeacherConsistencyFlag[]; flag_count: number;
}

export interface GradeBoundaryPriorityTopic {
  topic_name: string; current_average: number;
  exam_weight_percent: number; priority_score: number;
}
export interface GradeBoundaryWhatIf {
  student_id: number; status?: string;
  predicted_average?: number; predicted_grade?: string | null;
  next_grade?: string | null; points_needed?: number;
  priority_topics?: GradeBoundaryPriorityTopic[];
}

export interface DashboardSummary {
  total_students: number; total_classrooms: number;
  total_exams: number; at_risk_count: number; overall_average: number | null;
  recent_exams: { id: number; title: string; exam_type: ExamType; exam_date: string; term: TermType; subject: string | null }[];
  grade_distribution?: { A: number; B: number; C: number; D: number; F: number };
  classroom_averages?: { classroom: string; average: number; student_count: number }[];
  recent_exam_stats?: { id: number; title: string; exam_date: string; average: number | null; pass_rate: number | null }[];
  subject_averages?: { subject: string; code: string; color: string; average: number; pass_rate: number; student_count: number; exam_count: number }[];
  teacher_stats?: { teacher: string; email: string; average: number; pass_rate: number; exam_count: number; student_count: number }[];
}

export interface PaginatedResponse<T> {
  count: number; next: string | null; previous: string | null; results: T[];
}

// ── Topic Intelligence ───────────────────────────────────────────────────
export interface TopicIntelligenceEntry {
  topic_id: number; topic_name: string; subject_id: number | null; subject_name: string | null;
  color: string; attempts: number; student_count: number;
  average: number; highest: number; lowest: number;
  trend: 'improving' | 'declining' | 'stable'; trend_slope: number; difficulty_rank: number;
}

export interface TopicClassroomMatrix {
  classrooms: { id: number; name: string }[];
  topics: { id: number; name: string }[];
  matrix: (number | null)[][];
}

export interface TopicIntelligenceOverview {
  topics: TopicIntelligenceEntry[];
  classroom_matrix: TopicClassroomMatrix;
  most_improved: TopicIntelligenceEntry[];
  most_declined: TopicIntelligenceEntry[];
}

export interface TopicDistributionBucket { range: string; count: number }

export interface TopicDistribution {
  topic_id: number;
  histogram: TopicDistributionBucket[];
  timeline: { date: string; percentage: number }[];
  summary: {
    attempts: number; student_count: number;
    average: number; highest: number; lowest: number;
    trend: 'improving' | 'declining' | 'stable';
  } | null;
}

// ── Gamification ─────────────────────────────────────────────────────────
export interface Badge {
  id: number; code: string; name: string; description: string;
  icon: string; criteria_type: string; threshold: number;
}

export interface StudentBadgeAward {
  id: number; badge: Badge; exam: number | null; exam_title: string | null; awarded_at: string;
}

export interface StudentStreak {
  current_streak: number; longest_streak: number;
  last_exam: number | null; last_exam_title: string | null;
  last_exam_date: string | null; last_result_passed: boolean | null;
  updated_at: string;
}

export interface StudentProgress {
  student_id: number; student_name: string;
  streak: StudentStreak; badges: StudentBadgeAward[];
}

// ── Seating chart ─────────────────────────────────────────────────────────
export interface SeatingChartSeat {
  row: number; col: number;
  student: { id: number; name: string; student_id: string; group_id: number | null } | null;
}

export interface SeatingChart {
  classroom_id: number; classroom_name: string;
  rows: number; cols: number; capacity: number; seated_count: number;
  seats: SeatingChartSeat[];
  unseated: { id: number; name: string; student_id: string }[];
  warnings: string[];
}

// ── Tournaments ──────────────────────────────────────────────────────────
export type TournamentMode = 'individual' | 'stream';
export type TournamentStatus = 'draft' | 'registration_open' | 'registration_closed' | 'live' | 'completed' | 'cancelled';

export interface Tournament {
  id: number; title: string; codename: string; description: string;
  mode: TournamentMode; exam: number; exam_title: string; exam_date: string; exam_is_published: boolean;
  classroom: number; classroom_name: string; status: TournamentStatus;
  registration_opens_at: string | null; registration_deadline: string;
  max_entrants: number | null; is_public: boolean; created_by_name: string | null;
  finalized_at: string | null; entry_count: number; challenge_count: number;
  created_at: string; updated_at: string;
}

export interface TournamentEntry {
  id: number; display_name: string; entrant_type: 'student' | 'stream';
  student_id: number | null; stream_id: number | null;
  classroom_name: string | null; seed_average: number | null;
  withdrawn: boolean; live_score: number | null;
}

export interface Challenge {
  id: number; tournament: number; label: string; entries: TournamentEntry[];
  status: 'pending' | 'resolved' | 'void'; winner: TournamentEntry | null; is_tie: boolean;
  initiated_by_name: string | null; created_at: string; resolved_at: string | null;
  compatibility?: CompatibilityCheck | null;
  compatibility_note: string;
}

export interface CompatibilityCheck {
  compatible: boolean | null; gap: number | null; threshold: number; reason: string | null;
  entry_a: { id: number; name: string; average: number | null };
  entry_b: { id: number; name: string; average: number | null };
}

export interface SuggestedGroupMember {
  id: number; student_id: number; name: string; average: number;
}

export interface SuggestedGroup {
  members: SuggestedGroupMember[]; size: number; gap: number; compatible: boolean;
  ai_note: string | null;
}

export interface SuggestedGroupBye { entry_id: number; student_id: number; name: string; average: number }

export interface SuggestedGroupsResponse {
  proposed_groups: SuggestedGroup[];
  byes: SuggestedGroupBye[];
  insufficient_history: { entry_id: number; student_id: number; name: string }[];
  threshold: number;
  group_size: number;
  ai_used: boolean;
  ai_attempted: boolean;
  ai_error: string | null;
}

export interface AutoMatchResponse {
  created: Challenge[];
  skipped_incompatible: SuggestedGroup[];
  byes: SuggestedGroupBye[];
  insufficient_history: { entry_id: number; student_id: number; name: string }[];
  ai_used: boolean;
  ai_attempted: boolean;
  ai_error: string | null;
}

export interface EntryResult {
  id: number; entry: TournamentEntry; score_percentage: number | null; rank: number | null;
  prior_average: number | null; delta: number | null;
  is_rising_star: boolean; is_champion: boolean; is_absent: boolean; computed_at: string;
}

export interface TournamentDetail extends Tournament {
  entries: TournamentEntry[]; challenges: Challenge[]; leaderboard: EntryResult[];
}

export interface TournamentDossier {
  tournament: Tournament; leaderboard: EntryResult[];
  champion: EntryResult | null; rising_stars: EntryResult[]; challenges: Challenge[];
}

export interface TournamentIntel {
  tournaments_completed: number; total_entrants: number; total_challenges_fought: number;
  most_decorated: { name: string; count: number }[];
  most_duel_wins: { name: string; wins: number }[];
  rising_stars: { name: string; tournament: string; delta: number | null }[];
  stream_leaderboard: { name: string; titles: number; entries: number; average_score: number | null }[];
}

export interface MyTournamentEntryRow {
  tournament: Tournament; entry_id: number; seed_average: number | null;
  live_score: number | null; result: EntryResult | null;
}

export interface TournamentAnalytics {
  entrant_count: number; classroom_size: number; participation_rate: number | null;
  absentee_count: number;
  score_distribution: { band: string; count: number }[];
  entrant_average: number | null; classroom_average: number | null; pass_rate: number | null;
  closest_duel: { challenge_id: number; label: string; gap: number } | null;
  biggest_upset: { challenge_id: number; label: string; winner: string; seed_gap: number } | null;
  top_riser: { name: string; delta: number } | null;
}

export interface HeadToHeadRecord {
  student_a: { id: number; name: string }; student_b: { id: number; name: string };
  a_wins: number; b_wins: number; ties: number; total_duels: number;
  history: {
    challenge_id: number; tournament: string; label: string;
    winner: string | null; is_tie: boolean; resolved_at: string | null;
  }[];
}

// ── Leagues (skill-band groups + promotion) ─────────────────────────────────
export type LeagueIntervalMode = 'auto' | 'manual';
export type LeaguePromotionMode = 'auto' | 'manual';
export type LeagueSeasonStatus = 'draft' | 'active' | 'archived';
export type PromotionEventStatus = 'pending' | 'approved' | 'rejected' | 'auto_applied';

export interface LeagueSeason {
  id: number; title: string; classroom: number; classroom_name: string;
  baseline_exam: number; baseline_exam_title: string;
  interval_mode: LeagueIntervalMode; band_width: number; promotion_mode: LeaguePromotionMode;
  status: LeagueSeasonStatus; created_by_name: string | null;
  group_count: number; member_count: number; pending_promotion_count: number;
  created_at: string; updated_at: string; activated_at: string | null;
}

export interface LeagueGroup {
  id: number; season: number; name: string; min_mark: number; max_mark: number;
  order: number; color: string; icon: string; member_count: number; created_at: string;
}

export interface LeagueMembership {
  id: number; season: number; student: number; student_name: string; student_code: string;
  group: number; group_name: string; group_color: string; group_order: number;
  placement_score: number; latest_score: number | null; latest_exam: number | null;
  is_promotion_pending: boolean; pending_target_group: number | null;
  pending_target_group_name: string | null; pending_trigger_score: number | null;
  is_top_tier: boolean; joined_at: string; updated_at: string;
}

export interface LeagueSeasonDetail extends LeagueSeason {
  groups: LeagueGroup[]; memberships: LeagueMembership[];
}

export interface PromotionEvent {
  id: number; membership: number; season: number; student: number; student_name: string;
  from_group: number; from_group_name: string; to_group: number; to_group_name: string;
  trigger_exam: number; trigger_exam_title: string; trigger_score: number;
  status: PromotionEventStatus; decided_by_name: string | null; decided_at: string | null;
  created_at: string;
}

export type TrendLabel = 'improving' | 'declining' | 'stable';

export interface LeagueBandMemberTrend {
  membership_id: number; student_id: number; student_name: string;
  latest_score: number | null; placement_score: number;
  trend: TrendLabel | null; distance_to_promotion: number | null; is_promotion_pending: boolean;
}

export interface LeagueBandStat {
  group_id: number; name: string; order: number; color: string; icon: string;
  min_mark: number; max_mark: number; member_count: number; average_score: number | null;
  members: LeagueBandMemberTrend[]; climbers: LeagueBandMemberTrend[];
  rising_count: number; declining_count: number; stable_count: number;
}

export interface LeagueAnalytics {
  season_id: number; total_members: number; band_stats: LeagueBandStat[];
  pending_promotions: {
    membership_id: number; student_id: number; student_name: string;
    current_group: string; target_group: string | null; trigger_score: number | null;
  }[];
  promotions_staged: number; promotions_applied: number; promotions_rejected: number;
  promotion_rate: number | null;
}

export interface TrendRosterRow {
  student_id: number; student_name: string; student_code: string; exams_counted: number;
  first_percentage: number; latest_percentage: number; delta: number; slope: number; trend: TrendLabel;
}

export interface ClassroomTrendRoster {
  classroom_id: number;
  improving: TrendRosterRow[]; declining: TrendRosterRow[]; stable: TrendRosterRow[];
  insufficient_data: (Omit<TrendRosterRow, 'trend'>)[];
  summary: { improving_count: number; declining_count: number; stable_count: number; insufficient_data_count: number };
}

export interface HallOfFame {
  top_tier: { student_id: number; student_name: string; classroom: string; season_title: string; group_name: string; score: number | null }[];
  season_champions: { season_id: number; season_title: string; classroom: string; student_id: number; student_name: string; group_name: string; score: number | null }[];
  most_promoted: { student_id: number; student_name: string; promotion_count: number }[];
  generated_at: string;
}

// ── Interventions (slow-learner staged improvement plans) ──────────────────
export type InterventionProgramStatus = 'active' | 'completed' | 'discontinued';
export type InterventionStageStatus = 'pending' | 'active' | 'completed' | 'skipped';

export interface InterventionStage {
  id: number; program: number; order: number; title: string; description: string;
  status: InterventionStageStatus; measured_before: number | null; measured_after: number | null;
  improvement: number | null; is_locked: boolean; notes: string;
  started_at: string | null; completed_at: string | null;
}

export interface InterventionProgram {
  id: number; student: number; student_name: string; student_code: string;
  classroom: number; classroom_name: string; subject: number | null;
  status: InterventionProgramStatus; trigger_reason: string;
  baseline_average: number; latest_average: number | null; improvement: number | null;
  stage_count: number; completed_stage_count: number; current_stage_title: string | null;
  created_by_name: string | null; started_at: string; completed_at: string | null; updated_at: string;
}

export interface InterventionProgramDetail extends InterventionProgram {
  stages: InterventionStage[];
}

export interface SlowLearnerCandidate {
  student_id: number; student_name: string; student_code: string;
  exam_count: number; slope: number; early_average: number; recent_average: number;
  overall_average: number; trend: 'flat' | 'falling';
}

export interface InterventionAnalytics {
  active_count: number; completed_count: number; discontinued_count: number;
  average_improvement: number | null; success_rate: number | null;
  leaderboard: { student_id: number; student_name: string; improvement: number | null; baseline_average: number; latest_average: number | null }[];
}

