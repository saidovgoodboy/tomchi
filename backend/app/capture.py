"""ANPR kadrlar oqimi uchun qaror mashinasi.

Har bir motion event uchun bitta ``CaptureSession`` yaratiladi. Kadrlar 1 s
oraliqda keladi; har kadrda plate nomzodi yoki ``None`` (raqam topilmadi)
beriladi.

Qaror qoidalari (loyiha talablariga muvofiq):

- Kamida ``min_frames`` kadr tahlil qilinmaguncha hech qanday finalizatsiya
  bo'lmaydi (bitta omadli kadr 100% bersa ham visit yozilmaydi).
- So'nggi ``window_size`` kadrda eng ko'p takrorlangan raqam ulushi
  ``agreement_threshold`` dan yuqori bo'lsa -> ``finalized``.
- Ketma-ket ``no_plate_abort_streak`` kadrda raqam topilmasa -> ``aborted``
  (soxta harakat).
- ``max_frames`` yoki ``max_session_seconds`` chegarasiga yetganda ->
  best-effort (raqam bo'lsa ``pending``, yo'qsa ``aborted``).
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import time
from typing import Literal


@dataclass(frozen=True)
class Decision:
    status: Literal["continue", "finalized", "pending", "aborted"]
    plate: str | None = None
    votes: int = 0
    agreement: float = 0.0
    reason: str = ""

    @property
    def terminal(self) -> bool:
        return self.status != "continue"


class CaptureSession:
    def __init__(
        self,
        event_id: str,
        *,
        min_frames: int = 5,
        window_size: int = 5,
        agreement_threshold: float = 0.8,
        max_frames: int = 15,
        max_session_seconds: float = 20.0,
        no_plate_abort_streak: int = 5,
    ) -> None:
        self.event_id = event_id
        self.min_frames = min_frames
        self.window_size = window_size
        self.agreement_threshold = agreement_threshold
        self.max_frames = max_frames
        self.max_session_seconds = max_session_seconds
        self.no_plate_abort_streak = no_plate_abort_streak

        # Oyna har kadrni (plate yoki None) saqlaydi: None "mos emas" deb
        # maxrajga kiradi, ya'ni bitta xira kadr 80% ga to'sqinlik qiladi.
        self.window: deque[str | None] = deque(maxlen=window_size)
        self.frames_seen = 0
        self.no_plate_streak = 0
        self.started_at = time.monotonic()
        self._decision: Decision | None = None

    @property
    def finished(self) -> bool:
        return self._decision is not None

    @property
    def decision(self) -> Decision | None:
        return self._decision

    def on_frame(self, plate: str | None, now: float | None = None) -> Decision:
        """Yangi kadr natijasini qabul qilib, qarorni qaytaradi.

        Terminal qaror (finalized/pending/aborted) chiqqandan keyin session
        "yopishadi" — keyingi kadrlar bir xil qarorni qaytaradi.
        """
        if self._decision is not None:
            return self._decision

        self.frames_seen += 1
        if plate is None:
            self.no_plate_streak += 1
        else:
            self.no_plate_streak = 0
        self.window.append(plate)

        current = now if now is not None else time.monotonic()

        # Soxta harakat: uzoq vaqt raqam topilmadi.
        if self.no_plate_streak >= self.no_plate_abort_streak:
            self._decision = Decision(status="aborted", reason="no_plate")
            return self._decision

        # Minimal dalil yig'ilgach bir xillikni tekshiramiz.
        if self.frames_seen >= self.min_frames:
            top, count = self._majority()
            agreement = count / len(self.window)
            if agreement >= self.agreement_threshold:
                self._decision = Decision(
                    status="finalized",
                    plate=top,
                    votes=count,
                    agreement=agreement,
                )
                return self._decision

        # Chegara: maksimal kadr yoki vaqt.
        elapsed = current - self.started_at
        if self.frames_seen >= self.max_frames or elapsed >= self.max_session_seconds:
            self._decision = self._best_effort()
            return self._decision

        return Decision(status="continue")

    def _majority(self) -> tuple[str | None, int]:
        plates = [p for p in self.window if p is not None]
        if not plates:
            return None, 0
        top, count = Counter(plates).most_common(1)[0]
        return top, count

    def _best_effort(self) -> Decision:
        plates = [p for p in self.window if p is not None]
        if not plates:
            return Decision(status="aborted", reason="no_reading")
        top, count = Counter(plates).most_common(1)[0]
        return Decision(
            status="pending",
            plate=top,
            votes=count,
            agreement=count / len(self.window),
            reason="agreement_not_reached",
        )
