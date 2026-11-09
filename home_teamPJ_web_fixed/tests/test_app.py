"""Lightweight route smoke tests for the Home Team PJ web app.

Run from the project directory with: python -m unittest discover -s tests -v
This test module uses a disposable SQLite database named smoke_test.db.
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///smoke_test.db"
os.environ.setdefault("SECRET_KEY", "test-only-secret-key")
os.environ.pop("OPENAI_API_KEY", None)

import unittest
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash
from app import app, db, User, Result, week_monday


class AppSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    def setUp(self):
        with app.app_context():
            db.drop_all()
            db.create_all()
            user = User(
                user_id="smoke-user",
                display_name="テストユーザー",
                password_hash=generate_password_hash("test-password-123"),
            )
            db.session.add(user)
            db.session.commit()
        self.client = app.test_client()
        response = self.client.post(
            "/login",
            data={"user_id": "smoke-user", "password": "test-password-123"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_all_main_pages_load(self):
        for path in ("/dashboard", "/schedules", "/records", "/analysis", "/locations"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_weekly_review_with_and_without_records(self):
        empty = self.client.get("/analysis")
        self.assertEqual(empty.status_code, 200)

        with app.app_context():
            user = User.query.filter_by(user_id="smoke-user").first()
            monday = week_monday(date.today())
            start = datetime.combine(monday, datetime.min.time()) + timedelta(hours=9)
            db.session.add(Result(
                user_id=user.id,
                result_date=monday,
                activity="勉強",
                detail="テスト記録",
                duration_minutes=60,
                start=start,
                end=start + timedelta(hours=1),
                source="manual",
            ))
            db.session.commit()

        populated = self.client.get("/analysis")
        self.assertEqual(populated.status_code, 200)
        self.assertIn("ランキング".encode(), populated.data)

    def test_invalid_week_query_falls_back_instead_of_500(self):
        response = self.client.get("/analysis?week=not-a-date")
        self.assertEqual(response.status_code, 200)

    def test_ai_endpoint_has_non_api_fallback(self):
        response = self.client.post("/analysis/ai", data={"week": date.today().isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.is_json)
        self.assertTrue(response.get_json().get("ok"))


if __name__ == "__main__":
    unittest.main()
