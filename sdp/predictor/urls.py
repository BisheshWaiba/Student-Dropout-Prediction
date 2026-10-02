from django.urls import path
from django.contrib.auth.views import LogoutView

from . import views

app_name = "predictor"

urlpatterns = [
    path("", views.home, name="home"),
    path("account/login/", views.account_login, name="login"),
    path("account/register/", views.register, name="register"),
    path("account/", views.account, name="account"),
    path("account/logout/", LogoutView.as_view(), name="logout"),
    path("predict/", views.predict_view, name="predict"),
    path("api/predict/", views.api_predict, name="api_predict"),
    path("api/model-info/", views.api_model_info, name="api_model_info"),
    path("api/history/", views.api_history, name="api_history"),
    path("api/dashboard/", views.api_dashboard, name="api_dashboard"),
    path("result/<int:pk>/", views.result, name="result"),
    path("history/", views.history, name="history"),
    path("history/export/", views.export_csv, name="export_csv"),
    path("history/<int:pk>/delete/", views.delete_prediction, name="delete"),
]
