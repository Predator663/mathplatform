"""
The fixed set of system badges. Single source of truth used both by the
data migration that seeds the Badge table and (indirectly, via the DB rows
it creates) by services.evaluate_badges — kept here as plain data rather
than admin-editable so behavior can't silently drift from what a Badge row
claims to require.

criteria_type meanings:
  exams_taken   — total published, non-absent exams scored >= threshold
  streak        — current pass-streak >= threshold
  perfect_score — scored 100% on any single exam
  comeback      — the very next exam after a fail was a pass
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
