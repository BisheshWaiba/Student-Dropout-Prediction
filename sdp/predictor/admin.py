from django.contrib import admin

from .models import Prediction


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ("id", "student_ref", "predicted_label", "prob_dropout", "prob_enrolled",
                    "prob_graduate", "created_at")
    list_filter = ("predicted_label", "created_at")
    search_fields = ("student_ref",)
    readonly_fields = ("created_at",)
