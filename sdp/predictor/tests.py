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


class HomePageTests(TestCase):
    def setUp(self):
        if not MODEL_OK:
            self.skipTest("Model files not found in ml_model/")
        self.client.force_login(User.objects.create_user(username="home-user", password="StrongPass123!"))

    def test_accuracy_is_shown_as_a_percentage(self):
        accuracy = ml.get_meta()["metrics"]["accuracy"] * 100
        response = self.client.get(reverse("predictor:home"))
        self.assertContains(response, f"{accuracy:.1f}%")
        self.assertNotContains(response, f"{accuracy / 100:.2f}%")


class AccountTests(TestCase):
    def test_registration_login_and_logout(self):
        response = self.client.post(reverse("predictor:register"), {
            "username": "new-user",
            "email": "new-user@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        })
        self.assertRedirects(response, reverse("predictor:home"))
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(User.objects.get(username="new-user").email, "new-user@example.com")

        self.client.post(reverse("predictor:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

        response = self.client.post(reverse("predictor:login"), {
            "username": "new-user",
            "password": "StrongPass123!",
        })
        self.assertRedirects(response, reverse("predictor:home"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_registration_requires_a_valid_email(self):
        base = {"username": "no-email", "password1": "StrongPass123!", "password2": "StrongPass123!"}
        for email in ("", "not-an-email"):
            response = self.client.post(reverse("predictor:register"), {**base, "email": email})
            self.assertEqual(response.status_code, 200, email)
            self.assertIn("email", response.context["form"].errors, email)
        self.assertFalse(User.objects.filter(username="no-email").exists())

    def test_protected_pages_redirect_to_login(self):
        response = self.client.get(reverse("predictor:predict"))
        self.assertRedirects(response, f"{reverse('predictor:login')}?next={reverse('predictor:predict')}")

    def test_every_page_requires_login_except_login_and_register(self):
        login_url = reverse("predictor:login")
        pages = [reverse(f"predictor:{n}") for n in ("home", "predict", "history", "export_csv", "account")]
        pages += [reverse("schema"), reverse("swagger-ui")]
        for url in pages:
            response = self.client.get(url)
            self.assertRedirects(response, f"{login_url}?next={url}", fetch_redirect_response=False, msg_prefix=url)

    def test_api_requires_login(self):
        # DRF views bypass LoginRequiredMiddleware; they answer anonymous clients with a JSON 403.
        for name in ("api_model_info", "api_history", "api_dashboard"):
            self.assertEqual(self.client.get(reverse(f"predictor:{name}")).status_code, 403, name)
        response = self.client.post(reverse("predictor:api_predict"), GOOD, content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Prediction.objects.count(), 0)

    def test_login_and_register_pages_are_public(self):
        for name in ("login", "register"):
            self.assertEqual(self.client.get(reverse(f"predictor:{name}")).status_code, 200, name)

    def test_navbar_links_depend_on_login_state(self):
        response = self.client.get(reverse("predictor:login"))
        self.assertContains(response, reverse("predictor:register"))
        self.assertNotContains(response, f'href="{reverse("predictor:history")}"')
        self.assertNotContains(response, f'href="{reverse("predictor:predict")}"')

        self.client.force_login(User.objects.create_user(username="nav-user", password="StrongPass123!"))
        response = self.client.get(reverse("predictor:home"))
        self.assertContains(response, f'href="{reverse("predictor:history")}"')
        self.assertContains(response, f'href="{reverse("predictor:predict")}"')

    def test_login_only_follows_safe_next_urls(self):
        User.objects.create_user(username="next-user", password="StrongPass123!")
        creds = {"username": "next-user", "password": "StrongPass123!"}
        login_url = reverse("predictor:login")

        response = self.client.post(f"{login_url}?next={reverse('predictor:history')}", creds)
        self.assertRedirects(response, reverse("predictor:history"))

        self.client.post(reverse("predictor:logout"))
        for unsafe in ("https://evil.example/", "//evil.example/"):
            response = self.client.post(f"{login_url}?next={unsafe}", creds)
            self.assertRedirects(response, reverse("predictor:home"), msg_prefix=unsafe)
            self.client.post(reverse("predictor:logout"))

    def test_logout_returns_to_login_page(self):
        self.client.force_login(User.objects.create_user(username="logout-user", password="StrongPass123!"))
        response = self.client.post(reverse("predictor:logout"))
        self.assertRedirects(response, reverse("predictor:login"))

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
