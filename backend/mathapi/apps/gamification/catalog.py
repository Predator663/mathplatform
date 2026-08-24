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

# Tournament badges — seeded by migrations/0006_seed_tournament_badges.py.
# criteria_type meanings (evaluated in services.evaluate_badges):
#   tournament_participations — total tournaments registered for (any mode)
#   tournament_match_wins     — total resolved head-to-head challenges won
#   tournament_titles         — total #1-overall tournament finishes
#   tournament_undefeated     — event flag: won every challenge in one tournament (2+)
#   tournament_giant_slayer   — event flag: beat an opponent with a much higher seed average
#   tournament_rising_star    — event flag: scored far above own prior average in a tournament
#   tournament_flawless_duel  — event flag: won a head-to-head challenge with a 100% score
#   tournament_underdog       — event flag: won a duel while seeded below the opponent
TOURNAMENT_BADGE_CATALOG = [
    {
        'code': 'tournament_recruit', 'name': 'Recruit',
        'description': 'Registered for your first tournament.',
        'icon': 'shield', 'criteria_type': 'tournament_participations', 'threshold': 1,
    },
    {
        'code': 'tournament_veteran', 'name': 'Veteran Competitor',
        'description': 'Registered for 5 tournaments.',
        'icon': 'shield-check', 'criteria_type': 'tournament_participations', 'threshold': 5,
    },
    {
        'code': 'tournament_duelist', 'name': 'Duelist',
        'description': 'Won your first head-to-head challenge.',
        'icon': 'swords', 'criteria_type': 'tournament_match_wins', 'threshold': 1,
    },
    {
        'code': 'tournament_gladiator', 'name': 'Gladiator',
        'description': 'Won 3 head-to-head challenges.',
        'icon': 'swords', 'criteria_type': 'tournament_match_wins', 'threshold': 3,
    },
    {
        'code': 'tournament_warlord', 'name': 'Warlord',
        'description': 'Won 10 head-to-head challenges.',
        'icon': 'crown', 'criteria_type': 'tournament_match_wins', 'threshold': 10,
    },
    {
        'code': 'tournament_champion', 'name': 'Tournament Champion',
        'description': 'Finished #1 overall in a tournament.',
        'icon': 'trophy', 'criteria_type': 'tournament_titles', 'threshold': 1,
    },
    {
        'code': 'tournament_dynasty', 'name': 'Dynasty',
        'description': 'Finished #1 overall in 3 tournaments.',
        'icon': 'trophy', 'criteria_type': 'tournament_titles', 'threshold': 3,
    },
    {
        'code': 'tournament_undefeated', 'name': 'Undefeated',
        'description': 'Won every challenge you fought in a single tournament.',
        'icon': 'shield-check', 'criteria_type': 'tournament_undefeated', 'threshold': 0,
    },
    {
        'code': 'tournament_giant_slayer', 'name': 'Giant Slayer',
        'description': 'Defeated an opponent with a far higher seed average.',
        'icon': 'zap', 'criteria_type': 'tournament_giant_slayer', 'threshold': 0,
    },
    {
        'code': 'tournament_rising_star', 'name': 'Rising Star',
        'description': 'Scored far above your own prior average in a tournament.',
        'icon': 'sparkles', 'criteria_type': 'tournament_rising_star', 'threshold': 0,
    },
    {
        'code': 'tournament_flawless_duel', 'name': 'Flawless Victory',
        'description': 'Won a head-to-head challenge with a perfect 100% score.',
        'icon': 'star', 'criteria_type': 'tournament_flawless_duel', 'threshold': 0,
    },
    {
        'code': 'tournament_underdog', 'name': 'Underdog Story',
        'description': 'Won a challenge as the lower-seeded competitor.',
        'icon': 'trending-up', 'criteria_type': 'tournament_underdog', 'threshold': 0,
    },
]

# League badges — seeded by migrations/0007_seed_league_intervention_badges.py.
# criteria_type meanings (evaluated in services.evaluate_badges):
#   league_promotion  — total approved/auto-applied league promotions >= threshold
#   league_top_tier   — event flag: currently sits in the highest band of any league season
LEAGUE_BADGE_CATALOG = [
    {
        'code': 'league_promoted', 'name': 'Promoted',
        'description': 'Moved up to a stronger league group.',
        'icon': 'trending-up', 'criteria_type': 'league_promotion', 'threshold': 1,
    },
    {
        'code': 'league_serial_climber', 'name': 'Serial Climber',
        'description': 'Earned 3 league promotions.',
        'icon': 'arrow-up-circle', 'criteria_type': 'league_promotion', 'threshold': 3,
    },
    {
        'code': 'league_top_tier', 'name': 'Top Tier',
        'description': 'Reached the highest band in a league.',
        'icon': 'crown', 'criteria_type': 'league_top_tier', 'threshold': 0,
    },
]

# Intervention badges — seeded by the same migration.
# criteria_type meanings:
#   intervention_completed  — event flag: finished every stage of an intervention program
#   intervention_turnaround — event flag: improved 10+ points from baseline to program close
INTERVENTION_BADGE_CATALOG = [
    {
        'code': 'intervention_completed', 'name': 'Comeback Plan Complete',
        'description': 'Completed every stage of an intervention programme.',
        'icon': 'check-circle', 'criteria_type': 'intervention_completed', 'threshold': 0,
    },
    {
        'code': 'intervention_turnaround', 'name': 'Turnaround',
        'description': 'Improved by 10 or more points across an intervention programme.',
        'icon': 'rocket', 'criteria_type': 'intervention_turnaround', 'threshold': 0,
    },
]
