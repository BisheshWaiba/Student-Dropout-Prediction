from django import forms
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm

# Hard, domain-based limits (independent of the training-data min/max)
LIMITS = {
    "age_at_enrollment": (15, 80),
    "admission_grade": (0, 200),
    "previous_qualification_grade": (0, 200),
    "curricular_units_1st_sem_grade": (0, 20),
    "curricular_units_2nd_sem_grade": (0, 20),
    "curricular_units_1st_sem_enrolled": (0, 30),
    "curricular_units_1st_sem_approved": (0, 30),
    "curricular_units_2nd_sem_enrolled": (0, 30),
    "curricular_units_2nd_sem_approved": (0, 30),
}

BINARY_CHOICES = {"gender": [("1", "Male"), ("0", "Female")]}
DEFAULT_YES_NO = [("1", "Yes"), ("0", "No")]

# Short hints for yes/no fields whose label alone is ambiguous
BINARY_HINTS = {"debtor": "Has unpaid debts", "displaced": "Lives away from home"}

GROUPS = [
    ("Student background", "Age, gender and living situation.",
     ["age_at_enrollment", "gender", "displaced"]),
    ("Admission", "How the student entered the course. Grades are on a 0 to 200 scale.",
     ["admission_grade", "previous_qualification_grade"]),
    ("Finances", "Scholarship, debt and tuition status.",
     ["scholarship_holder", "debtor", "tuition_fees_up_to_date"]),
    ("First semester", "Course units and average grade. Grades are on a 0 to 20 scale.",
     ["curricular_units_1st_sem_enrolled", "curricular_units_1st_sem_approved",
      "curricular_units_1st_sem_grade"]),
    ("Second semester", "Course units and average grade for semester 2.",
     ["curricular_units_2nd_sem_enrolled", "curricular_units_2nd_sem_approved",
      "curricular_units_2nd_sem_grade"]),
]


def build_field(f):
    name, kind = f["name"], f["type"]
    if kind == "binary":
        choices = [("", "Select...")] + BINARY_CHOICES.get(name, DEFAULT_YES_NO)
        return forms.TypedChoiceField(label=f["label"], choices=choices, coerce=int, empty_value=None,
                                      help_text=BINARY_HINTS.get(name, ""))
    lo, hi = LIMITS.get(name, (f["min"], f["max"]))
    hint = f"Between {lo:g} and {hi:g}"
    if name.endswith("_approved"):
        hint += ", not above units enrolled"
    common = dict(label=f["label"], min_value=lo, max_value=hi, help_text=hint)
    if kind == "int":
        return forms.IntegerField(**common)
    return forms.FloatField(widget=forms.NumberInput(attrs={"step": "0.1"}), **common)


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label="Email", max_length=254,
                             widget=forms.EmailInput(attrs={"autocomplete": "email"}))

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")


class EmailChangeForm(forms.Form):
    email = forms.EmailField(label="Email address", max_length=254,
                             widget=forms.EmailInput(attrs={"autocomplete": "email"}))


class AccountPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Django autofocuses this field, which would scroll the Account page down to it on every load.
        self.fields["old_password"].widget.attrs.pop("autofocus", None)
        self.fields["old_password"].label = "Current password"
        self.fields["new_password2"].label = "Confirm new password"
        self.fields["new_password2"].help_text = ""


class AccountDeleteForm(forms.Form):
    password = forms.CharField(
        label="Confirm with your password",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Incorrect password.")
        return password

    def clean(self):
        data = super().clean()
        if self.user.is_superuser:
            raise forms.ValidationError("Admin accounts can't be deleted here. Use the Django admin instead.")
        return data


class PredictionForm(forms.Form):
    student_ref = forms.CharField(
        label="Student name / ID (optional)", required=False, max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "e.g. STU-1024", "autocomplete": "off"}))

    def __init__(self, *args, meta, **kwargs):
        super().__init__(*args, **kwargs)
        self.feature_names = []
        for f in meta["features"]:
            self.fields[f["name"]] = build_field(f)
            self.feature_names.append(f["name"])

    def grouped_fields(self):
        groups = []
        for title, description, names in GROUPS:
            bound = [self[n] for n in names if n in self.fields]
            if bound:
                groups.append((title, description, bound))
        return groups

    def clean(self):
        data = super().clean()
        for sem in ("1st", "2nd"):
            enrolled = data.get(f"curricular_units_{sem}_sem_enrolled")
            approved = data.get(f"curricular_units_{sem}_sem_approved")
            if enrolled is not None and approved is not None and approved > enrolled:
                self.add_error(f"curricular_units_{sem}_sem_approved",
                               "Approved units cannot be more than enrolled units.")
        return data
