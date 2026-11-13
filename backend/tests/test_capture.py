import unittest

from app.capture import CaptureSession, Decision


class CaptureSessionTests(unittest.TestCase):
    def feed(self, session, plates):
        """plates ro'yxatini ketma-ket yuborib, oxirgi qarorni qaytaradi."""
        result = None
        for plate in plates:
            result = session.on_frame(plate)
        return result

    def test_single_100_percent_frame_does_not_finalize(self):
        session = CaptureSession("evt")
        decision = session.on_frame("01A123BC")
        self.assertEqual(decision.status, "continue")
        self.assertFalse(session.finished)

    def test_five_identical_frames_finalize(self):
        session = CaptureSession("evt")
        decision = self.feed(session, ["01A123BC"] * 5)
        self.assertEqual(decision.status, "finalized")
        self.assertEqual(decision.plate, "01A123BC")
        self.assertEqual(decision.votes, 5)
        self.assertEqual(decision.agreement, 1.0)

    def test_four_of_five_agree_finalizes(self):
        session = CaptureSession("evt")
        decision = self.feed(session, ["01A123BC", "01A123BC", "01A123BC", "01A123BC", None])
        self.assertEqual(decision.status, "finalized")
        self.assertEqual(decision.plate, "01A123BC")
        self.assertEqual(decision.agreement, 0.8)

    def test_three_of_five_continues(self):
        session = CaptureSession("evt")
        decision = self.feed(session, ["01A123BC", "01A123BC", "01A123BC", "02B456CD", "02B456CD"])
        self.assertEqual(decision.status, "continue")
        self.assertFalse(session.finished)

    def test_no_plate_frames_lower_agreement(self):
        # 3 bir xil + 2 xira = 3/5 = 0.6 -> davom etadi.
        session = CaptureSession("evt")
        decision = self.feed(session, ["01A123BC", "01A123BC", "01A123BC", None, None])
        self.assertEqual(decision.status, "continue")

    def test_no_plate_streak_aborts(self):
        session = CaptureSession("evt")
        decision = self.feed(session, [None, None, None, None, None])
        self.assertEqual(decision.status, "aborted")
        self.assertEqual(decision.reason, "no_plate")

    def test_max_frames_best_effort_pending(self):
        # Hech qachon 80% ga yetmaydigan aralash oqim.
        session = CaptureSession("evt")
        plates = []
        for i in range(15):
            plates.append("01A123BC" if i % 2 == 0 else "02B456CD")
        decision = self.feed(session, plates)
        self.assertEqual(decision.status, "pending")
        self.assertIsNotNone(decision.plate)

    def test_max_frames_abort_when_no_reading(self):
        session = CaptureSession("evt", max_frames=15)
        # 15 kadrning hammasi raqamsiz, lekin ketma-ketlik abortedan oldin
        # no_plate_abort_streak ga yetadi — buni alohida sessiya bilan tekshiramiz.
        session2 = CaptureSession("evt2", no_plate_abort_streak=999, max_frames=15)
        decision = self.feed(session2, [None] * 15)
        self.assertEqual(decision.status, "aborted")
        self.assertEqual(decision.reason, "no_reading")

    def test_terminal_decision_is_sticky(self):
        session = CaptureSession("evt")
        decision = self.feed(session, ["01A123BC"] * 5)
        self.assertEqual(decision.status, "finalized")
        # Keyingi kadrlar bir xil qarorni qaytarishi kerak.
        again = session.on_frame("02B456CD")
        self.assertIs(again, decision)
        self.assertTrue(session.finished)

    def test_time_based_best_effort(self):
        session = CaptureSession("evt", max_frames=1000, max_session_seconds=20.0)
        # 6 kadr berib 80% ga yetmaymiz, keyin vaqtni 21 s deb beramiz.
        self.feed(session, ["01A123BC", "02B456CD", "01A123BC", "02B456CD", "01A123BC", "02B456CD"])
        decision = session.on_frame("01A123BC", now=session.started_at + 21.0)
        self.assertEqual(decision.status, "pending")


if __name__ == "__main__":
    unittest.main()
