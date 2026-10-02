from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from . import ml
from .models import Prediction

try:
    ml.load_artifacts()
    MODEL_OK = True
except ml.ModelNotReady:
    MODEL_OK = False

GOOD = {
    "student_ref": "T-1", "age_at_enrollment": 20, "gender": 1, "displaced": 1,
    "admission_grade": 130.5, "previous_qualification_grade": 128, "scholarship_holder": 0,
    "debtor": 0, "tuition_fees_up_to_date": 1,
    "curricular_units_1st_sem_enrolled": 6, "curricular_units_1st_sem_approved": 5,
    "curricular_units_1st_sem_grade": 12.5, "curricular_units_2nd_sem_enrolled": 6,
    "curricular_units_2nd_sem_approved": 5, "curricular_units_2nd_sem_grade": 12.0,
}


class PageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="page-user", password="StrongPass123!")
        self.client.force_login(self.user)

    def test_static_pages_load(self):
        for name in ("home", "predict", "history"):
            self.assertEqual(self.client.get(reverse(f"predictor:{name}")).status_code, 200, name)


class AccountTests(TestCase):
    def test_registration_login_and_logout(self):
        response = self.client.post(reverse("predictor:register"), {
            "username": "new-user",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })
        self.assertRedirects(response, reverse("predictor:home"))
        self.assertIn("_auth_user_id", self.client.session)

        self.client.post(reverse("predictor:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

        response = self.client.post(reverse("predictor:login"), {
            "username": "new-user",
            "password": "StrongPass123!",
        })
        self.assertRedirects(response, reverse("predictor:home"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_protected_pages_redirect_to_login(self):
        response = self.client.get(reverse("predictor:predict"))
        self.assertRedirects(response, f"{reverse('predictor:login')}?next={reverse('predictor:predict')}")

    def test_account_page_requires_login(self):
        self.client.force_login(User.objects.create_user(username="account-user", password="StrongPass123!"))
        response = self.client.get(reverse("predictor:account"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "account-user")


class PredictionTests(TestCase):
    def setUp(self):
        if not MODEL_OK:
            self.skipTest("Model files not found in ml_model/")
        self.user = User.objects.create_user(username="prediction-user", password="StrongPass123!")
        self.client.force_login(self.user)

    def test_api_predict_returns_json(self):
        r = self.client.post(reverse("predictor:api_predict"), GOOD, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertIn("predicted_label", payload)
        self.assertIn("probabilities", payload)
        self.assertAlmostEqual(sum(payload["probabilities"].values()), 1.0, places=5)

    def test_api_history_and_dashboard_return_json(self):
        self.client.post(reverse("predictor:api_predict"), GOOD, content_type="application/json")
        history = self.client.get(reverse("predictor:api_history"))
        dashboard = self.client.get(reverse("predictor:api_dashboard"))
        self.assertEqual(history.status_code, 200)
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("results", history.json())
        self.assertIn("total", dashboard.json())

    def test_valid_prediction_is_saved_and_shown(self):
        r = self.client.post(reverse("predictor:predict"), GOOD)
        self.assertEqual(Prediction.objects.count(), 1)
        obj = Prediction.objects.get()
        self.assertRedirects(r, reverse("predictor:result", args=[obj.pk]))
        self.assertAlmostEqual(obj.prob_dropout + obj.prob_enrolled + obj.prob_graduate, 1.0, places=5)
        self.assertEqual(self.client.get(reverse("predictor:result", args=[obj.pk])).status_code, 200)

    def test_approved_more_than_enrolled_rejected(self):
        bad = dict(GOOD, curricular_units_1st_sem_approved=9)
        r = self.client.post(reverse("predictor:predict"), bad)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Prediction.objects.count(), 0)

    def test_out_of_range_rejected(self):
        r = self.client.post(reverse("predictor:predict"), dict(GOOD, curricular_units_2nd_sem_grade=25))
        self.assertEqual(Prediction.objects.count(), 0)

    def test_history_export_delete(self):
        self.client.post(reverse("predictor:predict"), GOOD)
        pk = Prediction.objects.get().pk
        self.assertContains(self.client.get(reverse("predictor:history")), "T-1")
        csv_resp = self.client.get(reverse("predictor:export_csv"))
        self.assertIn("text/csv", csv_resp["Content-Type"])
        self.client.post(reverse("predictor:delete", args=[pk]))
        self.assertEqual(Prediction.objects.count(), 0)
