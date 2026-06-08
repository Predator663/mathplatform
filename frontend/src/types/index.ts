// ── Auth ──────────────────────────────────────────────────────────────────────
export type UserRole = 'super_admin' | 'teacher' | 'student' | 'parent';

export interface User {
  id: number; email: string; first_name: string; last_name: string;
  full_name: string; role: UserRole; is_active: boolean;
  date_joined: string; phone: string; avatar: string | null;
}

export interface AuthTokens { access: string; refresh: string; }
export interface LoginResponse extends AuthTokens { user: User; }

// ── Tanzania Curriculum ───────────────────────────────────────────────────────
export type EducationLevel = 'pre_primary' | 'primary' | 'o_level' | 'a_level' | 'technical';
export type ClassStream = 'general' | 'science' | 'arts' | 'commerce' | 'technical';

export interface GradeLevel {
  id: number; name: string; short_name: string;
  education_level: EducationLevel; education_level_display: string;
  order: number; necta_exam: string; math_subject: string;
}

export interface Classroom {
  id: number; name: string;
  grade_level: number; grade_level_name: string; grade_level_short: string;
  education_level: EducationLevel; education_level_display: string;
  stream: ClassStream; stream_display: string;
  academic_year: string; teachers: number[]; teacher_names: string[];
  is_active: boolean; student_count: number;
  necta_exam: string; math_subject: string; created_at: string;
}

export interface StudentProfile {
  id: number; student_id: string; full_name: string;
  first_name: string; last_name: string; email: string;
  classroom: number | null; classroom_name: string | null;
  grade_level: string | null; education_level: EducationLevel | null;
  date_of_birth: string | null; enrollment_date: string; is_active: boolean;
  notes: string; index_number: string; parent_name: string;
  parent_phone: string; district: string; region: string;
}

// ── Exams ─────────────────────────────────────────────────────────────────────
export type ExamType =
  | 'monthly_test' | 'mid_term' | 'terminal' | 'mock'
  | 'necta' | 'psle' | 'csee' | 'acsee' | 'diagnostic';

export type TermType = 'term_1' | 'term_2' | 'term_3' | 'annual';
export type TopicLevel = 'primary' | 'o_level' | 'a_level' | 'all';

export interface MathTopic {
  id: number; name: string; description: string;
  color: string; level: TopicLevel; order: number;
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

// ── Analytics ─────────────────────────────────────────────────────────────────
export interface StudentSummary {
  student_id: number; student_name: string; student_code: string;
  classroom: string | null; total_exams: number;
  average_percentage: number | null; highest_percentage: number;
  lowest_percentage: number; pass_rate: number;
  trend: 'improving' | 'stable' | 'declining' | 'no_data';
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

export interface ExamSummary {
  exam_id: number; exam_title: string; exam_type: ExamType; term: TermType;
  exam_date: string; student_count: number; average: number;
  highest: number; lowest: number; pass_rate: number; std_dev: number;
}

export interface StudentRanking {
  student_id: number; student_name: string; student_code: string;
  average: number; exams_taken: number; rank: number;
}

export interface ClassAnalytics {
  classroom_id: number; classroom_name: string; grade_level: string;
  exam_summaries: ExamSummary[]; overall_average: number | null;
  student_rankings: StudentRanking[]; at_risk_students: StudentRanking[];
  top_performers: StudentRanking[]; distribution: Record<string, number>;
}

export interface AtRiskStudent {
  student_id: number; student_name: string; student_code: string;
  classroom: string | null; recent_average: number; recent_scores: number[];
  flags: { below_threshold: boolean; declining: boolean };
}

export interface DashboardSummary {
  total_students: number; total_classrooms: number;
  total_exams: number; at_risk_count: number; overall_average: number | null;
  recent_exams: { id: number; title: string; exam_type: ExamType; exam_date: string; term: TermType }[];
}

export interface PaginatedResponse<T> {
  count: number; next: string | null; previous: string | null; results: T[];
}
