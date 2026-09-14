"""Tests for the V2 review workflow state machine."""

import unittest

from app.models.v2.review import ReviewState, REVIEW_TRANSITIONS


class TestReviewStateMachine(unittest.TestCase):
    """Validate the review state transition map."""

    def test_initial_state_is_ai_generated(self):
        """Default starting state is AI_GENERATED."""
        self.assertEqual(ReviewState.AI_GENERATED.value, "AI_GENERATED")

    def test_all_states_present_in_transitions(self):
        """Every ReviewState must have an entry in the transition map."""
        for state in ReviewState:
            self.assertIn(state, REVIEW_TRANSITIONS)

    def test_forward_transitions_valid(self):
        """Check the happy-path forward flow: AI_GENERATED -> ... -> APPROVED."""
        path = [
            (ReviewState.AI_GENERATED, ReviewState.AUTO_VALIDATED),
            (ReviewState.AUTO_VALIDATED, ReviewState.UNDER_REVIEW),
            (ReviewState.UNDER_REVIEW, ReviewState.FIELD_VERIFIED),
            (ReviewState.FIELD_VERIFIED, ReviewState.APPROVED),
        ]
        for from_state, to_state in path:
            allowed = REVIEW_TRANSITIONS[from_state]
            self.assertIn(
                to_state, allowed,
                f"{from_state.value} -> {to_state.value} should be a valid transition",
            )

    def test_approved_has_no_transitions(self):
        """APPROVED is a terminal state."""
        self.assertEqual(REVIEW_TRANSITIONS[ReviewState.APPROVED], [])

    def test_invalid_backward_not_allowed_from_approved(self):
        """Cannot go backward from APPROVED."""
        self.assertNotIn(ReviewState.FIELD_VERIFIED, REVIEW_TRANSITIONS[ReviewState.APPROVED])

    def test_reject_from_under_review(self):
        """UNDER_REVIEW can be rejected back to AI_GENERATED."""
        self.assertIn(ReviewState.AI_GENERATED, REVIEW_TRANSITIONS[ReviewState.UNDER_REVIEW])

    def test_reject_from_field_verified(self):
        """FIELD_VERIFIED can go back to UNDER_REVIEW for re-review."""
        self.assertIn(ReviewState.UNDER_REVIEW, REVIEW_TRANSITIONS[ReviewState.FIELD_VERIFIED])

    def test_skip_not_allowed(self):
        """Cannot skip states e.g. AI_GENERATED -> UNDER_REVIEW."""
        self.assertNotIn(ReviewState.UNDER_REVIEW, REVIEW_TRANSITIONS[ReviewState.AI_GENERATED])
        self.assertNotIn(ReviewState.APPROVED, REVIEW_TRANSITIONS[ReviewState.AI_GENERATED])

    def test_all_transitions_target_valid_states(self):
        """Every target in the transition map must be a valid ReviewState."""
        for from_state, targets in REVIEW_TRANSITIONS.items():
            for target in targets:
                self.assertIsInstance(target, ReviewState)


class TestReviewDecisionModel(unittest.TestCase):
    """Validate the ReviewDecision ORM model metadata."""

    def test_tablename(self):
        from app.models.v2.review import ReviewDecision
        self.assertEqual(ReviewDecision.__tablename__, "v2_review_decisions")

    def test_columns_exist(self):
        from app.models.v2.review import ReviewDecision
        columns = {c.name for c in ReviewDecision.__table__.columns}
        expected = {"id", "project_id", "from_state", "to_state", "reviewer_id", "note", "created_at"}
        self.assertTrue(expected.issubset(columns), f"Missing columns: {expected - columns}")


if __name__ == "__main__":
    unittest.main()
