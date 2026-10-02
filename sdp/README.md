# Student Dropout & Academic Success Predictor (Django + scikit-learn)

A Django web app that predicts whether a student will **Dropout**, remain **Enrolled** or **Graduate**,
using a model trained on the UCI dataset _Predict Students' Dropout and Academic Success_ (id 697).

## Features

- Prediction form (14 fields) built automatically from `model_meta.json`, with validation
  (value ranges, approved units cannot exceed enrolled units)
- Result page: predicted outcome, probabilities, dropout-risk level, suggested actions, student-vs-average table
- Prediction history: search, filter by outcome, pagination, delete, CSV export
- Dashboard: totals, high-risk count, charts (predictions by outcome, training class distribution, feature importance)
- Model page: metrics, model comparison table, feature list, notebook figures

## Setup (Windows / macOS / Linux)

```bash
# 1. (recommended) create a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux

# 2. install dependencies
pip install -r requirements.txt
```

**Important:** `.pkl` files only load reliably on the same scikit-learn version used for training.
Check yours with `python -c "import sklearn; print(sklearn.__version__)"` in the environment where you ran the
notebook, and install exactly that version, e.g. `pip install scikit-learn==1.8.0`.

```bash
# 3. copy your trained model files into ml_model/  (see ml_model/PUT_MODEL_FILES_HERE.txt)
#    student_model.pkl, model_meta.json, model_comparison.csv

# 4. (optional) copy the notebook's figures/*.png into predictor/static/predictor/figures/
#    so they appear on the Model page

# 5. create the database
python manage.py migrate

# 6. run
python manage.py runserver
```

Open http://127.0.0.1:8000/

Run the automated tests (they use your real model): `python manage.py test`

## Project structure

```
config/            Django settings + root URLs
predictor/
  ml.py            loads the .pkl / .json and makes predictions
  models.py        Prediction model (saved results)
  forms.py         dynamic prediction form + validation
  views.py         home, predict, result, history, export, dashboard, model info
  templates/       Bootstrap 5 pages
  tests.py         automated tests
ml_model/          <- put student_model.pkl and model_meta.json here
```

## How it works

1. The notebook trains the model and saves a full scikit-learn pipeline (scaler + classifier) as `student_model.pkl`,
   plus `model_meta.json` (feature names, labels, class names, metrics).
2. `predictor/ml.py` loads both once. The form fields are generated from the metadata.
3. On submit, the values become a one-row DataFrame -> `predict_proba` -> saved to the database -> result page.

## Limitations

- Second-semester data is required, so this is an early-warning tool mid-course, not on enrollment day.
- The _Enrolled_ class is the hardest to predict.
- Predictions are statistical estimates to support advisors, not final decisions about a student.

## Before deploying publicly

Set `DJANGO_DEBUG=0`, a real `DJANGO_SECRET_KEY`, and `DJANGO_ALLOWED_HOSTS`; run `python manage.py collectstatic`.
The Bootstrap and Chart.js libraries load from a CDN, so the app needs an internet connection to look right.

## Dataset citation

Realinho, V., Vieira Martins, M., Machado, J., & Baptista, L. (2021). _Predict Students' Dropout and Academic
Success_ [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5MC89 (CC BY 4.0)
