from django.db import models
from django.contrib.auth.models import User

from .ml import risk_level


class Prediction(models.Model):
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="predictions")
    student_ref = models.CharField("Student name / ID", max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    inputs = models.JSONField()
    predicted_label = models.CharField(max_length=20)
    prob_dropout = models.FloatField()
    prob_enrolled = models.FloatField()
    prob_graduate = models.FloatField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        who = self.student_ref or f"Prediction #{self.pk}"
        return f"{who} -> {self.predicted_label}"

    @property
    def confidence(self):
        return max(self.prob_dropout, self.prob_enrolled, self.prob_graduate)

    @property
    def risk(self):
        return risk_level(self.prob_dropout)
