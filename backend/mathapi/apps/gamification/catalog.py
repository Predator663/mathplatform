"""
The fixed set of system badges. Single source of truth used both by the
data migration that seeds the Badge table and (indirectly, via the DB rows
it creates) by services.evaluate_badges — kept here as plain data rather
than admin-editable so behavior can't silently drift from what a Badge row
claims to require.

criteria_type meanings:
  exams_taken   — total published, non-absent exams scored >= threshold
  streak        — current exam pass-streak >= threshold
  perfect_score — scored 100% on any single exam
  comeback      — the very next exam after a fail was a pass
  quiz_streak   — current daily-quiz participation streak >= threshold
  quiz_perfect  — scored 100% on any single daily quiz
"""

BADGE_CATALOG = [
    {
        'code': 'first_exam', 'name': 'First Steps',
        'description': 'Completed your first exam.',
        'icon': 'flag', 'criteria_type': 'exams_taken', 'threshold': 1,
    },
    {
        'code': 'streak_3', 'name': 'On a Roll',
        'description': 'Passed 3 exams in a row.',
        'icon': 'flame', 'criteria_type': 'streak', 'threshold': 3,
    },
    {
        'code': 'streak_5', 'name': 'Consistency Champion',
        'description': 'Passed 5 exams in a row.',
        'icon': 'flame', 'criteria_type': 'streak', 'threshold': 5,
    },
    {
        'code': 'streak_10', 'name': 'Unstoppable',
        'description': 'Passed 10 exams in a row.',
        'icon': 'flame', 'criteria_type': 'streak', 'threshold': 10,
    },
    {
        'code': 'perfect_score', 'name': 'Perfect Score',
        'description': 'Scored 100% on an exam.',
        'icon': 'star', 'criteria_type': 'perfect_score', 'threshold': 100,
    },
    {
        'code': 'comeback', 'name': 'Comeback',
        'description': 'Bounced back from a fail to a pass on the next exam.',
        'icon': 'trending-up', 'criteria_type': 'comeback', 'threshold': 0,
    },
]

# Daily-quiz badges — seeded separately (see migrations/0003_seed_quiz_badges.py)
# so an already-deployed database gets them via a new migration rather than
# requiring 0002 to be edited after the fact.
QUIZ_BADGE_CATALOG = [
    {
        'code': 'quiz_streak_5', 'name': 'Daily Grinder',
        'description': 'Attempted 5 daily quizzes in a row.',
        'icon': 'flame', 'criteria_type': 'quiz_streak', 'threshold': 5,
    },
    {
        'code': 'quiz_streak_20', 'name': 'Quiz Marathon',
        'description': 'Attempted 20 daily quizzes in a row.',
        'icon': 'flame', 'criteria_type': 'quiz_streak', 'threshold': 20,
    },
    {
        'code': 'quiz_perfect', 'name': 'Quiz Ace',
        'description': 'Scored 100% on a daily quiz.',
        'icon': 'star', 'criteria_type': 'quiz_perfect', 'threshold': 100,
    },
]
