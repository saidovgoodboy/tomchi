import base64
import json
import os
import subprocess
import unittest
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image

os.environ.update(
    {
        "DATABASE_URL": "sqlite://",
        "DEVICE_KEY": "hardware-test-key",
        "ADMIN_USERNAME": "admin-test",
        "ADMIN_PASSWORD": "test-password",
        "ADMIN_TOKEN_SECRET": "test-token-secret-with-at-least-32-bytes",
        "ADMIN_ORIGINS": "http://localhost:5173",
    }
)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth
from app.crud import create_visit_for_car, get_display_text, is_valid_plate, press_bonus
from app.db import Base, get_db
from app.main import app
from app.anpr import (
    OCRUnavailableError,
    PlateCandidate,
    candidate_from_tsv,
    recognize_plate,
)
from app.models import BonusPulse, Car, DetectionRecord, DeviceLog, Visit, WashBox


class AuthAndBonusRulesTests(unittest.TestCase):
    def setUp(self):
        with auth._login_attempts_lock:
            auth._login_attempts.clear()
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        def override_get_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_admin_login_token_is_separate_from_device_key(self):
        login = self.client.post(
            "/api/auth/login",
            json={"username": "admin-test", "password": "test-password"},
        )
        self.assertEqual(login.status_code, 200)
        token = login.json()["access_token"]

        self.assertEqual(self.client.get("/api/stats").status_code, 401)
        self.assertEqual(
            self.client.get("/api/stats", headers={"X-Device-Key": "hardware-test-key"}).status_code,
            401,
        )
        self.assertEqual(
            self.client.get("/api/stats", headers={"Authorization": f"Bearer {token}"}).status_code,
            200,
        )
        encoded_payload = token.split(".", 1)[0]
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        )
        with patch("app.auth.time.time", return_value=payload["exp"] + 1):
            self.assertEqual(
                self.client.get("/api/stats", headers={"Authorization": f"Bearer {token}"}).status_code,
                401,
            )
        self.assertEqual(
            self.client.get("/api/stats", headers={"Authorization": "Bearer invalid"}).status_code,
            401,
        )

    def test_device_routes_require_device_key_not_admin_token(self):
        login = self.client.post(
            "/api/auth/login",
            json={"username": "admin-test", "password": "test-password"},
        )
        token = login.json()["access_token"]
        self.assertEqual(
            self.client.get("/api/display", headers={"Authorization": f"Bearer {token}"}).status_code,
            401,
        )
        response = self.client.get("/api/display", headers={"X-Device-Key": "hardware-test-key"})
        self.assertEqual(response.status_code, 200)
        image_response = self.client.post(
            "/api/detect-image",
            headers={"Authorization": f"Bearer {token}"},
            data={"event_id": "event-1", "frame_index": "0", "frame_count": "1"},
            files={"image": ("frame.jpg", b"\xff\xd8\xff", "image/jpeg")},
        )
        self.assertEqual(image_response.status_code, 401)

    def test_admin_routes_reject_missing_and_device_authentication(self):
        requests = [
            ("get", "/api/settings", None),
            ("put", "/api/settings", {"bonus_amount": 20000}),
            ("get", "/api/boxes", None),
            ("post", "/api/boxes", {"id": "box-2", "name": "Box 2"}),
            ("get", "/api/boxes/box-1/test", None),
            ("post", "/api/boxes/box-1/test/start", None),
            ("post", "/api/boxes/box-1/test/pulses", {"amount": 1000}),
            ("post", "/api/boxes/box-1/test/finish", None),
            ("get", "/api/visits", None),
            ("put", "/api/visits/1/plate", {"plate": "01A123BC"}),
            ("get", "/api/cars", None),
            ("post", "/api/detect", {"plate": "01A123BC"}),
            ("get", "/api/detections", None),
            ("get", "/api/detections/1/image", None),
            ("get", "/api/boxes/box-1/live-frame", None),
        ]
        for method, path, body in requests:
            with self.subTest(method=method, path=path):
                kwargs = {"headers": {"X-Device-Key": "hardware-test-key"}}
                if body is not None:
                    kwargs["json"] = body
                response = getattr(self.client, method)(path, **kwargs)
                self.assertEqual(response.status_code, 401)

    def test_wrong_admin_password_is_rejected(self):
        response = self.client.post(
            "/api/auth/login",
            json={"username": "admin-test", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 401)

    def test_admin_login_is_rate_limited(self):
        for _ in range(auth.LOGIN_RATE_LIMIT):
            response = self.client.post(
                "/api/auth/login",
                json={"username": "admin-test", "password": "wrong"},
            )
            self.assertEqual(response.status_code, 401)

        limited = self.client.post(
            "/api/auth/login",
            json={"username": "admin-test", "password": "test-password"},
        )
        self.assertEqual(limited.status_code, 429)
        self.assertIn("retry-after", limited.headers)

    def test_cors_allows_configured_origin_without_credentials(self):
        response = self.client.options(
            "/api/stats",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")
        self.assertNotIn("access-control-allow-credentials", response.headers)

        rejected = self.client.options(
            "/api/stats",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertNotIn("access-control-allow-origin", rejected.headers)

    def test_pulse_settings_are_saved_and_sent_to_device(self):
        login = self.client.post(
            "/api/auth/login",
            json={"username": "admin-test", "password": "test-password"},
        )
        admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        defaults = self.client.get("/api/settings", headers=admin_headers)
        self.assertEqual(defaults.status_code, 200)
        self.assertEqual(defaults.json()["pulse_polarity"], "HIGH")
        self.assertEqual(defaults.json()["pulse_frequency_ms"], 100)

        created_box = self.client.post(
            "/api/boxes",
            headers=admin_headers,
            json={"id": "box-2", "name": "Box 2"},
        )
        self.assertEqual(created_box.status_code, 200)

        updated = self.client.put(
            "/api/settings?box_id=box-1",
            headers=admin_headers,
            json={
                "pulse_polarity": "LOW",
                "pulse_frequency_ms": 50,
                "display_idle_text": "BOX BO'SH",
                "display_visit_label": "KELDI",
                "display_reward_label": "SOVG'A",
                "display_remaining_label": "QOLDI",
                "display_finished_text": "TUGADI",
                "display_currency_label": "SUM",
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["pulse_polarity"], "LOW")
        self.assertEqual(updated.json()["pulse_frequency_ms"], 50)
        self.assertEqual(updated.json()["display_idle_text"], "BOX BO'SH")
        self.assertEqual(updated.json()["display_finished_text"], "TUGADI")

        box_two_update = self.client.put(
            "/api/settings?box_id=box-2",
            headers=admin_headers,
            json={"pulse_polarity": "HIGH", "pulse_frequency_ms": 200},
        )
        self.assertEqual(box_two_update.status_code, 200)

        box_one_settings = self.client.get(
            "/api/settings?box_id=box-1",
            headers=admin_headers,
        )
        box_two_settings = self.client.get(
            "/api/settings?box_id=box-2",
            headers=admin_headers,
        )
        self.assertEqual(box_one_settings.json()["pulse_polarity"], "LOW")
        self.assertEqual(box_one_settings.json()["pulse_frequency_ms"], 50)
        self.assertEqual(box_two_settings.json()["pulse_polarity"], "HIGH")
        self.assertEqual(box_two_settings.json()["pulse_frequency_ms"], 200)
        self.assertEqual(box_two_settings.json()["display_idle_text"], "AVTOMOBIL YO'Q")
        self.assertEqual(box_two_settings.json()["display_remaining_label"], "MUKOFOT QOLDI")

        db = self.session_factory()
        try:
            car = Car(plate="01A123BC")
            db.add(car)
            db.flush()
            db.add(
                Visit(
                    car_id=car.id,
                    box_id="box-1",
                    visit_no=1,
                    bonus_total=5_000,
                    bonus_left=5_000,
                    is_active_bonus=1,
                )
            )
            db.commit()
        finally:
            db.close()

        device_settings = self.client.get(
            "/api/display",
            headers={"X-Device-Key": "hardware-test-key"},
        )
        self.assertEqual(device_settings.status_code, 200)
        self.assertEqual(device_settings.json()["pulse_polarity"], "LOW")
        self.assertEqual(device_settings.json()["pulse_frequency_ms"], 50)
        self.assertEqual(
            device_settings.json()["text"],
            "01A123BC - 1-KELDI! SOVG'A 5 000 SUM",
        )
        self.assertEqual(device_settings.json()["display_remaining_label"], "QOLDI")
        self.assertEqual(device_settings.json()["display_finished_text"], "TUGADI")

        box_two_device_settings = self.client.get(
            "/api/display",
            headers={
                "X-Device-Key": "hardware-test-key",
                "X-Box-Id": "box-2",
            },
        )
        self.assertEqual(box_two_device_settings.json()["pulse_polarity"], "HIGH")
        self.assertEqual(box_two_device_settings.json()["pulse_frequency_ms"], 200)
        self.assertEqual(box_two_device_settings.json()["text"], "AVTOMOBIL YO'Q")

        invalid = self.client.put(
            "/api/settings?box_id=box-1",
            headers=admin_headers,
            json={"pulse_polarity": "MEDIUM", "pulse_frequency_ms": 75},
        )
        self.assertEqual(invalid.status_code, 422)
        invalid_display_text = self.client.put(
            "/api/settings?box_id=box-1",
            headers=admin_headers,
            json={"display_idle_text": "АВТО"},
        )
        self.assertEqual(invalid_display_text.status_code, 422)

    def test_box_test_queues_pulses_without_using_customer_bonus(self):
        db = self.session_factory()
        try:
            box = WashBox(id="box-1", name="Box 1")
            car = Car(plate="01A123BC")
            db.add_all([box, car])
            db.flush()
            db.add(
                Visit(
                    car_id=car.id,
                    box_id=box.id,
                    visit_no=1,
                    bonus_total=20000,
                    bonus_left=20000,
                    is_active_bonus=1,
                )
            )
            db.commit()
        finally:
            db.close()

        login = self.client.post(
            "/api/auth/login",
            json={"username": "admin-test", "password": "test-password"},
        )
        admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        started = self.client.post(
            "/api/boxes/box-1/test/start",
            headers=admin_headers,
        )
        self.assertEqual(started.status_code, 200)
        self.assertTrue(started.json()["active"])

        invalid_amount = self.client.post(
            "/api/boxes/box-1/test/pulses",
            headers=admin_headers,
            json={"amount": 1500},
        )
        self.assertEqual(invalid_amount.status_code, 422)

        queued = self.client.post(
            "/api/boxes/box-1/test/pulses",
            headers=admin_headers,
            json={"amount": 5000},
        )
        self.assertEqual(queued.status_code, 200)
        self.assertEqual(queued.json()["pending_amount"], 5000)

        duplicate = self.client.post(
            "/api/boxes/box-1/test/pulses",
            headers=admin_headers,
            json={"amount": 1000},
        )
        self.assertEqual(duplicate.status_code, 409)

        refused_bonus = self.client.post(
            "/api/bonus/press",
            headers={"X-Device-Key": "hardware-test-key"},
            json={},
        )
        self.assertFalse(refused_bonus.json()["ok"])
        self.assertEqual(refused_bonus.json()["message"], "Box is in test mode")

        device_headers = {"X-Device-Key": "hardware-test-key"}
        first_poll = self.client.get("/api/display", headers=device_headers)
        self.assertTrue(first_poll.json()["test_mode"])
        self.assertEqual(first_poll.json()["test_pulse_count"], 5)
        second_poll = self.client.get("/api/display", headers=device_headers)
        self.assertEqual(second_poll.json()["test_pulse_count"], 0)

        queued_again = self.client.post(
            "/api/boxes/box-1/test/pulses",
            headers=admin_headers,
            json={"amount": 3000},
        )
        self.assertEqual(queued_again.status_code, 200)
        finished = self.client.post(
            "/api/boxes/box-1/test/finish",
            headers=admin_headers,
        )
        self.assertFalse(finished.json()["active"])
        self.assertIsNone(finished.json()["pending_amount"])
        final_poll = self.client.get("/api/display", headers=device_headers)
        self.assertFalse(final_poll.json()["test_mode"])
        self.assertEqual(final_poll.json()["test_pulse_count"], 0)

        db = self.session_factory()
        try:
            self.assertEqual(db.query(BonusPulse).count(), 0)
            self.assertEqual(db.query(Visit).one().bonus_left, 20000)
        finally:
            db.close()

    def test_ocr_candidate_is_stored_for_review_without_automatic_visit(self):
        image_buffer = BytesIO()
        Image.new("RGB", (320, 240), "white").save(image_buffer, format="JPEG")
        image_bytes = image_buffer.getvalue()
        candidates = [
            PlateCandidate(plate="01A123BC", confidence=0.76),
            PlateCandidate(plate="01A123BC", confidence=0.94),
        ]

        with TemporaryDirectory() as storage_dir:
            with (
                patch("app.main.settings.anpr_enabled", True),
                patch("app.main.settings.storage_dir", Path(storage_dir)),
                patch("app.main.recognize_plate", side_effect=candidates),
            ):
                first = self.client.post(
                    "/api/detect-image",
                    headers={"X-Device-Key": "hardware-test-key", "X-Box-Id": "box-1"},
                    data={"event_id": "ocr-event", "frame_index": "0", "frame_count": "2"},
                    files={"image": ("frame.jpg", image_bytes, "image/jpeg")},
                )
                second = self.client.post(
                    "/api/detect-image",
                    headers={"X-Device-Key": "hardware-test-key", "X-Box-Id": "box-1"},
                    data={"event_id": "ocr-event", "frame_index": "1", "frame_count": "2"},
                    files={"image": ("frame.jpg", image_bytes, "image/jpeg")},
                )

                self.assertEqual(first.status_code, 200)
                self.assertEqual(second.status_code, 200)
                self.assertEqual(second.json()["plate"], "01A123BC")
                self.assertAlmostEqual(second.json()["ocr_confidence"], 0.94)
                self.assertEqual(second.json()["status"], "pending")

                db = self.session_factory()
                try:
                    detection = db.query(DetectionRecord).one()
                    self.assertEqual(detection.plate, "01A123BC")
                    self.assertAlmostEqual(detection.ocr_confidence, 0.94)
                    self.assertEqual(db.query(Visit).count(), 0)
                    detection_id = detection.id
                finally:
                    db.close()

                login = self.client.post(
                    "/api/auth/login",
                    json={"username": "admin-test", "password": "test-password"},
                )
                admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
                detections = self.client.get("/api/detections", headers=admin_headers)
                self.assertEqual(detections.json()[0]["plate"], "01A123BC")
                confirmed = self.client.put(
                    f"/api/detections/{detection_id}/plate",
                    headers=admin_headers,
                    json={"plate": "01A123BC"},
                )
                self.assertEqual(confirmed.status_code, 200)
                db = self.session_factory()
                try:
                    self.assertEqual(db.query(Visit).count(), 1)
                finally:
                    db.close()

    def test_ocr_candidate_parser_handles_plate_layout_and_ocr_confusions(self):
        tsv = (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tconf\ttext\n"
            "5\t1\t1\t1\t1\t92.5\tOIA123BC\n"
        )
        candidate = candidate_from_tsv(tsv)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.plate, "01A123BC")
        self.assertAlmostEqual(candidate.confidence, 0.895)
        self.assertIsNone(candidate_from_tsv(tsv.replace("OIA123BC", "WASHONLY")))
        special_format = candidate_from_tsv(
            tsv.replace("OIA123BC", "12345ABC").replace("92.5", "96")
        )
        self.assertEqual(special_format.plate, "12345ABC")

    def test_local_ocr_adapter_preprocesses_jpeg_and_parses_tesseract_output(self):
        image_buffer = BytesIO()
        Image.new("RGB", (320, 240), "white").save(image_buffer, format="JPEG")
        tsv = (
            b"level\tpage_num\tblock_num\tpar_num\tline_num\tconf\ttext\n"
            b"5\t1\t1\t1\t1\t91\t01A123BC\n"
        )
        result = subprocess.CompletedProcess(
            args=["tesseract"],
            returncode=0,
            stdout=tsv,
            stderr=b"",
        )

        with (
            patch("app.anpr.shutil.which", return_value="/usr/bin/tesseract"),
            patch("app.anpr.subprocess.run", return_value=result) as run,
        ):
            candidate = recognize_plate(image_buffer.getvalue())

        self.assertEqual(candidate.plate, "01A123BC")
        self.assertEqual(run.call_args.kwargs["input"][:8], b"\x89PNG\r\n\x1a\n")

    def test_image_upload_survives_unavailable_local_ocr_engine(self):
        image_buffer = BytesIO()
        Image.new("RGB", (320, 240), "white").save(image_buffer, format="JPEG")

        with TemporaryDirectory() as storage_dir:
            with (
                patch("app.main.settings.anpr_enabled", True),
                patch("app.main.settings.storage_dir", Path(storage_dir)),
                patch(
                    "app.main.recognize_plate",
                    side_effect=OCRUnavailableError("Tesseract not installed"),
                ),
            ):
                response = self.client.post(
                    "/api/detect-image",
                    headers={"X-Device-Key": "hardware-test-key", "X-Box-Id": "box-1"},
                    data={"event_id": "ocr-unavailable", "frame_index": "0", "frame_count": "1"},
                    files={"image": ("frame.jpg", image_buffer.getvalue(), "image/jpeg")},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ocr_status"], "unavailable")
        self.assertIsNone(response.json()["plate"])

    def test_visit_list_includes_linked_detection_image_only(self):
        db = self.session_factory()
        try:
            box = WashBox(id="box-1", name="Box 1")
            pictured_car = Car(plate="01A123BC")
            manual_car = Car(plate="02B456CD")
            db.add_all([box, pictured_car, manual_car])
            db.flush()
            pictured_visit = Visit(
                car_id=pictured_car.id,
                box_id=box.id,
                visit_no=1,
                bonus_total=0,
                bonus_left=0,
                is_active_bonus=0,
            )
            manual_visit = Visit(
                car_id=manual_car.id,
                box_id=box.id,
                visit_no=1,
                bonus_total=0,
                bonus_left=0,
                is_active_bonus=0,
            )
            db.add_all([pictured_visit, manual_visit])
            db.flush()
            detection = DetectionRecord(
                box_id=box.id,
                event_key="pictured-event",
                image_key="pictured-image",
                visit_id=pictured_visit.id,
            )
            db.add(detection)
            db.commit()
            pictured_visit_id = pictured_visit.id
            manual_visit_id = manual_visit.id
            detection_id = detection.id
        finally:
            db.close()

        login = self.client.post(
            "/api/auth/login",
            json={"username": "admin-test", "password": "test-password"},
        )
        response = self.client.get(
            "/api/visits?box_id=box-1",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        self.assertEqual(response.status_code, 200)
        visits_by_id = {visit["id"]: visit for visit in response.json()}
        self.assertEqual(
            visits_by_id[pictured_visit_id]["image_url"],
            f"/api/detections/{detection_id}/image",
        )
        self.assertIsNone(visits_by_id[manual_visit_id]["image_url"])

    def test_plate_validation_accepts_only_ascii_formats(self):
        self.assertTrue(is_valid_plate("01A123BC"))
        self.assertTrue(is_valid_plate("12345ABC"))
        self.assertFalse(is_valid_plate("٠١A123BC"))
        self.assertFalse(is_valid_plate("01Å123BC"))
        self.assertFalse(is_valid_plate("01ſ123BC"))

    def test_p10_display_messages_are_uzbek(self):
        db = self.session_factory()
        try:
            self.assertEqual(get_display_text(db)["text"], "AVTOMOBIL YO'Q")
            car = Car(plate="01A123BC")
            db.add(car)
            db.flush()
            visit = Visit(
                car_id=car.id,
                box_id="box-1",
                visit_no=10,
                bonus_total=20_000,
                bonus_left=20_000,
                is_active_bonus=1,
            )
            db.add(visit)
            db.commit()
            self.assertEqual(
                get_display_text(db)["text"],
                "01A123BC - 10-KELISH! MUKOFOT 20 000 SO'M",
            )

            visit.is_active_bonus = 0
            db.commit()
            self.assertEqual(get_display_text(db)["text"], "01A123BC - 10-KELISH")
        finally:
            db.close()

    def test_other_car_duplicate_detection_expires_active_bonus(self):
        db = self.session_factory()
        try:
            box = WashBox(id="box-1", name="Box 1")
            owner = Car(plate="01A123BC")
            other = Car(plate="02B456CD")
            db.add_all([box, owner, other])
            db.flush()
            active_bonus = Visit(
                car_id=owner.id,
                box_id=box.id,
                created_at=datetime.utcnow() - timedelta(hours=2),
                visit_no=10,
                bonus_total=20_000,
                bonus_left=15_000,
                is_active_bonus=1,
            )
            duplicate_visit = Visit(
                car_id=other.id,
                box_id=box.id,
                created_at=datetime.utcnow() - timedelta(hours=1),
                visit_no=1,
            )
            db.add_all([active_bonus, duplicate_visit])
            db.commit()

            returned = create_visit_for_car(db, other, box.id)

            db.refresh(active_bonus)
            self.assertEqual(returned.id, duplicate_visit.id)
            self.assertEqual(active_bonus.bonus_left, 0)
            self.assertEqual(active_bonus.bonus_expired, 15_000)
            self.assertEqual(active_bonus.is_active_bonus, 0)
            self.assertEqual(
                db.query(DeviceLog).filter(DeviceLog.event == "bonus_expired").count(),
                1,
            )
        finally:
            db.close()

    def test_same_car_duplicate_detection_preserves_its_bonus(self):
        db = self.session_factory()
        try:
            box = WashBox(id="box-1", name="Box 1")
            owner = Car(plate="01A123BC")
            db.add_all([box, owner])
            db.flush()
            active_bonus = Visit(
                car_id=owner.id,
                box_id=box.id,
                created_at=datetime.utcnow() - timedelta(hours=1),
                visit_no=10,
                bonus_total=20_000,
                bonus_left=15_000,
                is_active_bonus=1,
            )
            db.add(active_bonus)
            db.commit()

            returned = create_visit_for_car(db, owner, box.id)

            db.refresh(active_bonus)
            self.assertEqual(returned.id, active_bonus.id)
            self.assertEqual(active_bonus.bonus_left, 15_000)
            self.assertEqual(active_bonus.is_active_bonus, 1)
        finally:
            db.close()

    def test_global_bonus_can_only_be_used_at_awarding_box(self):
        db = self.session_factory()
        try:
            first_box = WashBox(id="box-1", name="Box 1")
            second_box = WashBox(id="box-2", name="Box 2")
            owner = Car(plate="01A123BC")
            db.add_all([first_box, second_box, owner])
            db.flush()
            active_bonus = Visit(
                car_id=owner.id,
                box_id=first_box.id,
                visit_no=10,
                bonus_total=20_000,
                bonus_left=20_000,
                is_active_bonus=1,
            )
            db.add(active_bonus)
            db.commit()

            result = press_bonus(db, owner.plate, second_box.id)

            db.refresh(active_bonus)
            self.assertFalse(result["ok"])
            self.assertEqual(active_bonus.bonus_left, 20_000)
        finally:
            db.close()

    def _seed_active_bonus(self, plate: str = "01A123BC") -> int:
        db = self.session_factory()
        try:
            box = WashBox(id="box-1", name="Box 1")
            car = Car(plate=plate)
            db.add_all([box, car])
            db.flush()
            visit = Visit(
                car_id=car.id,
                box_id=box.id,
                visit_no=10,
                bonus_total=20_000,
                bonus_left=20_000,
                is_active_bonus=1,
            )
            db.add(visit)
            db.commit()
            return visit.id
        finally:
            db.close()

    def test_visit_timestamp_is_utc_with_z_suffix(self):
        self._seed_active_bonus()
        login = self.client.post(
            "/api/auth/login",
            json={"username": "admin-test", "password": "test-password"},
        )
        response = self.client.get(
            "/api/visits?box_id=box-1",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        self.assertEqual(response.status_code, 200)
        created_at = response.json()[0]["created_at"]
        self.assertTrue(created_at.endswith("Z"), created_at)
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        self.assertEqual(parsed.utcoffset(), timedelta(0))

    def test_bonus_press_is_idempotent_for_same_press_id(self):
        self._seed_active_bonus()
        headers = {"X-Device-Key": "hardware-test-key", "X-Box-Id": "box-1"}
        first = self.client.post("/api/bonus/press", json={"press_id": "press-abc-1"}, headers=headers)
        second = self.client.post("/api/bonus/press", json={"press_id": "press-abc-1"}, headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(first.json()["ok"])
        self.assertFalse(first.json()["duplicate"])
        self.assertTrue(second.json()["duplicate"])
        self.assertEqual(first.json()["amount"], second.json()["amount"])
        self.assertEqual(first.json()["bonus_left"], second.json()["bonus_left"])

        db = self.session_factory()
        try:
            self.assertEqual(db.query(BonusPulse).count(), 1)
        finally:
            db.close()

    def test_admin_can_refund_a_pulse_once(self):
        self._seed_active_bonus()
        headers = {"X-Device-Key": "hardware-test-key", "X-Box-Id": "box-1"}
        pressed = self.client.post("/api/bonus/press", json={"press_id": "press-refund-1"}, headers=headers)
        self.assertEqual(pressed.status_code, 200)
        bonus_after_press = pressed.json()["bonus_left"]

        login = self.client.post(
            "/api/auth/login",
            json={"username": "admin-test", "password": "test-password"},
        )
        admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        pulses = self.client.get("/api/pulses?box_id=box-1", headers=admin_headers)
        self.assertEqual(pulses.status_code, 200)
        pulse = pulses.json()[0]
        self.assertEqual(pulse["amount"], 5_000)
        self.assertIsNone(pulse["refunded_at"])

        refunded = self.client.post(f"/api/pulses/{pulse['id']}/refund", headers=admin_headers)
        self.assertEqual(refunded.status_code, 200)
        self.assertEqual(refunded.json()["bonus_left"], bonus_after_press + 5_000)

        again = self.client.post(f"/api/pulses/{pulse['id']}/refund", headers=admin_headers)
        self.assertEqual(again.status_code, 409)

    def test_health_reports_database_status(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["database_ok"])

    def _seed_three_visits(self) -> None:
        db = self.session_factory()
        try:
            box = WashBox(id="box-1", name="Box 1")
            db.add(box)
            db.flush()
            base = datetime(2026, 11, 12, 8, 0, 0)
            for index, plate in enumerate(["01A123BC", "02B456CD", "03C789DE"]):
                car = Car(plate=plate)
                db.add(car)
                db.flush()
                db.add(
                    Visit(
                        car_id=car.id,
                        box_id=box.id,
                        created_at=base + timedelta(minutes=index),
                        visit_no=1,
                    )
                )
            db.commit()
        finally:
            db.close()

    def _admin_headers(self) -> dict[str, str]:
        login = self.client.post(
            "/api/auth/login",
            json={"username": "admin-test", "password": "test-password"},
        )
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_visits_support_plate_search_and_offset(self):
        self._seed_three_visits()
        headers = self._admin_headers()

        filtered = self.client.get("/api/visits?box_id=box-1&plate=123", headers=headers)
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual([row["plate"] for row in filtered.json()], ["01A123BC"])

        page_one = self.client.get("/api/visits?box_id=box-1&limit=1&offset=0", headers=headers)
        page_two = self.client.get("/api/visits?box_id=box-1&limit=1&offset=1", headers=headers)
        self.assertEqual(len(page_one.json()), 1)
        self.assertEqual(len(page_two.json()), 1)
        self.assertNotEqual(page_one.json()[0]["id"], page_two.json()[0]["id"])

    def test_admin_actions_are_written_to_device_log(self):
        self._seed_active_bonus()
        headers = self._admin_headers()

        updated = self.client.put(
            "/api/settings?box_id=box-1",
            json={"bonus_amount": 30000},
            headers=headers,
        )
        self.assertEqual(updated.status_code, 200)

        db = self.session_factory()
        try:
            log = db.query(DeviceLog).filter(DeviceLog.event == "admin_settings_update").one()
            self.assertIn("amount=30000", log.payload)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
