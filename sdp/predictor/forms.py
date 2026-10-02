from django import forms

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

GROUPS = [
    ("Student background", ["age_at_enrollment", "gender", "displaced"]),
    ("Admission", ["admission_grade", "previous_qualification_grade"]),
    ("Finances", ["scholarship_holder", "debtor", "tuition_fees_up_to_date"]),
    ("First semester", ["curricular_units_1st_sem_enrolled", "curricular_units_1st_sem_approved",
                        "curricular_units_1st_sem_grade"]),
    ("Second semester", ["curricular_units_2nd_sem_enrolled", "curricular_units_2nd_sem_approved",
                         "curricular_units_2nd_sem_grade"]),
]


def build_field(f):
    name, kind = f["name"], f["type"]
    help_text = f["help"]
    if kind == "binary":
        choices = [("", "Select...")] + BINARY_CHOICES.get(name, DEFAULT_YES_NO)
        return forms.TypedChoiceField(label=f["label"], choices=choices, coerce=int, empty_value=None,
                                      help_text=help_text, widget=forms.Select(attrs={"class": "form-select"}))
    lo, hi = LIMITS.get(name, (f["min"], f["max"]))
    common = dict(label=f["label"], min_value=lo, max_value=hi,
                  help_text=f"{help_text}. Allowed: {lo:g} to {hi:g}.")
    if kind == "int":
        return forms.IntegerField(widget=forms.NumberInput(attrs={"class": "form-control"}), **common)
    return forms.FloatField(widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}), **common)


class PredictionForm(forms.Form):
    student_ref = forms.CharField(
        label="Student name / ID (optional)", required=False, max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. STU-1024"}))

    def __init__(self, *args, meta, **kwargs):
        super().__init__(*args, **kwargs)
        self.feature_names = []
        for f in meta["features"]:
            self.fields[f["name"]] = build_field(f)
            self.feature_names.append(f["name"])

    def grouped_fields(self):
        groups = []
        for title, names in GROUPS:
            bound = [self[n] for n in names if n in self.fields]
            if bound:
                groups.append((title, bound))
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
