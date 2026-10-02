import csv
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required, login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import ml
from .forms import PredictionForm
from .models import Prediction

ADVICE = {
    "Dropout": [
        "Arrange an academic counselling meeting as soon as possible.",
        "Review the student's financial situation (fees, scholarship, debts).",
        "Check which course units are failing and offer tutoring or a lighter workload.",
        "Follow up regularly (monthly) until the risk decreases.",
    ],
    "Enrolled": [
        "The student is likely to still be studying beyond the normal course length.",
        "Offer study-planning support and help with the remaining course units.",
        "Monitor progress each semester.",
    ],
    "Graduate": [
        "The student is on a good track to graduate.",
        "Keep encouraging steady progress; no special intervention is needed now.",
    ],
}

FIGURE_CAPTIONS = {
    "01_target_distribution.png": "Outcome distribution",
    "02_socioeconomic_vs_target.png": "Socio-economic factors vs outcome",
    "03_academic_vs_target.png": "Academic performance vs outcome",
    "04_age_admission.png": "Age and admission grade",
    "05_correlation_with_target.png": "Correlation with outcome",
    "06_model_comparison.png": "Model comparison",
    "07_confusion_matrix.png": "Confusion matrix",
    "08_feature_importance.png": "Feature importance",
}


def _meta_or_none():
    try:
        return ml.get_meta(), None
    except ml.ModelNotReady as exc:
        return None, str(exc)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_model_info(request):
    meta, error = _meta_or_none()
    if error:
        return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"meta": meta})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_history(request):
    qs = Prediction.objects.all().order_by("-created_at")
    items = []
    for p in qs:
        items.append({
            "id": p.pk,
            "student_ref": p.student_ref,
            "predicted_label": p.predicted_label,
            "created_at": p.created_at.isoformat(),
            "probabilities": {
                "Dropout": p.prob_dropout,
                "Enrolled": p.prob_enrolled,
                "Graduate": p.prob_graduate,
            },
        })
    return Response({"count": len(items), "results": items})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_dashboard(request):
    meta, _ = _meta_or_none()
    counts = {r["predicted_label"]: r["n"] for r in Prediction.objects.values("predicted_label").annotate(n=Count("id"))}
    avgs = Prediction.objects.aggregate(d=Avg("prob_dropout"), e=Avg("prob_enrolled"), g=Avg("prob_graduate"))
    high_risk = sum(1 for p in Prediction.objects.only("prob_dropout") if p.prob_dropout >= 0.5)
    return Response({
        "total": Prediction.objects.count(),
        "high_risk": high_risk,
        "average_probabilities": {
            "Dropout": float(avgs["d"] or 0),
            "Enrolled": float(avgs["e"] or 0),
            "Graduate": float(avgs["g"] or 0),
        },
        "predictions_by_label": {k: counts.get(k, 0) for k in ("Dropout", "Enrolled", "Graduate")},
        "class_distribution": meta["class_distribution"] if meta else {},
        "feature_importance": meta["feature_importance"] if meta else {},
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_predict(request):
    meta, error = _meta_or_none()
    if error:
        return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

    payload = request.data or {}
    if not isinstance(payload, dict):
        return Response({"error": "Expected a JSON object."}, status=status.HTTP_400_BAD_REQUEST)

    form = PredictionForm(data=payload, meta=meta)
    if not form.is_valid():
        return Response({"errors": form.errors}, status=status.HTTP_400_BAD_REQUEST)

    values = {name: form.cleaned_data[name] for name in form.feature_names}
    result = ml.predict(values)
    obj = Prediction.objects.create(
        owner=request.user if request.user.is_authenticated else None,
        student_ref=payload.get("student_ref", ""),
        inputs=values,
        predicted_label=result["label"],
        prob_dropout=result["probs"].get("Dropout", 0.0),
        prob_enrolled=result["probs"].get("Enrolled", 0.0),
        prob_graduate=result["probs"].get("Graduate", 0.0),
    )
    return Response({
        "prediction_id": obj.pk,
        "student_ref": obj.student_ref,
        "predicted_label": obj.predicted_label,
        "risk_level": ml.risk_level(obj.prob_dropout),
        "confidence": obj.confidence,
        "probabilities": {
            "Dropout": obj.prob_dropout,
            "Enrolled": obj.prob_enrolled,
            "Graduate": obj.prob_graduate,
        },
        "advice": ADVICE.get(obj.predicted_label, []),
    })


def home(request):
    meta, error = _meta_or_none()
    return render(request, "predictor/home.html", {"meta": meta, "model_error": error,
                                                   "accuracy_pct": meta["metrics"]["accuracy"] * 100 if meta else None,
                                                   "total": Prediction.objects.filter(owner=request.user).count()
                                                   if request.user.is_authenticated else 0})


@login_required
def predict_view(request):
    meta, error = _meta_or_none()
    if error:
        return render(request, "predictor/predict.html", {"model_error": error})

    if request.method == "POST":
        form = PredictionForm(request.POST, meta=meta)
        if form.is_valid():
            values = {n: form.cleaned_data[n] for n in form.feature_names}
            out = ml.predict(values)
            obj = Prediction.objects.create(
                owner=request.user,
                student_ref=form.cleaned_data.get("student_ref", ""),
                inputs=values,
                predicted_label=out["label"],
                prob_dropout=out["probs"].get("Dropout", 0.0),
                prob_enrolled=out["probs"].get("Enrolled", 0.0),
                prob_graduate=out["probs"].get("Graduate", 0.0),
            )
            return redirect("predictor:result", pk=obj.pk)
        messages.error(request, "Please correct the highlighted fields.")
    else:
        form = PredictionForm(meta=meta)
    return render(request, "predictor/predict.html", {"form": form})


@login_required
def result(request, pk):
    obj = get_object_or_404(Prediction, pk=pk, owner=request.user)
    meta, _ = _meta_or_none()
    comparison = []
    if meta:
        for f in meta["features"]:
            value = obj.inputs.get(f["name"])
            if value is None:
                continue
            if f["type"] == "binary":
                shown = ("Male" if value == 1 else "Female") if f["name"] == "gender" else ("Yes" if value == 1 else "No")
                avg = f"{f['mean'] * 100:.0f}% Yes" if f["name"] != "gender" else f"{f['mean'] * 100:.0f}% Male"
            else:
                shown = f"{value:g}"
                avg = f"{f['mean']:g}"
            comparison.append({"label": f["label"], "value": shown, "average": avg})
    return render(request, "predictor/result.html", {
        "p": obj,
        "probs": [("Dropout", obj.prob_dropout, "danger"), ("Enrolled", obj.prob_enrolled, "warning"),
                  ("Graduate", obj.prob_graduate, "success")],
        "advice": ADVICE.get(obj.predicted_label, []),
        "comparison": comparison,
    })


@login_required
def history(request):
    qs = Prediction.objects.filter(owner=request.user)
    outcome = request.GET.get("outcome", "")
    if outcome in ADVICE:
        qs = qs.filter(predicted_label=outcome)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(student_ref__icontains=q)
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "predictor/history.html",
                  {"page": page, "outcome": outcome, "q": q, "outcomes": list(ADVICE)})


@login_required
def export_csv(request):
    meta, _ = _meta_or_none()
    features = [f["name"] for f in meta["features"]] if meta else []
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="predictions.csv"'
    writer = csv.writer(response)
    writer.writerow(["id", "created_at", "student_ref", "predicted", "p_dropout", "p_enrolled",
                     "p_graduate"] + features)
    for p in Prediction.objects.filter(owner=request.user):
        writer.writerow([p.pk, p.created_at.strftime("%Y-%m-%d %H:%M"), p.student_ref, p.predicted_label,
                         round(p.prob_dropout, 4), round(p.prob_enrolled, 4), round(p.prob_graduate, 4)]
                        + [p.inputs.get(n, "") for n in features])
    return response


@login_required
@require_POST
def delete_prediction(request, pk):
    get_object_or_404(Prediction, pk=pk, owner=request.user).delete()
    messages.success(request, "Prediction deleted.")
    return redirect("predictor:history")


@login_not_required
def register(request):
    if request.user.is_authenticated:
        return redirect("predictor:account")
    form = UserCreationForm(request.POST or None)
    if form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your account is ready.")
        return redirect("predictor:home")
    return render(request, "predictor/register.html", {"form": form})


@login_not_required
def account_login(request):
    if request.user.is_authenticated:
        return redirect("predictor:account")
    form = AuthenticationForm(request, data=request.POST or None)
    if form.is_valid():
        login(request, form.get_user())
        # Every page now bounces here with ?next=..., so only follow it when it stays on this site.
        next_url = request.GET.get("next", "")
        if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
            return redirect(next_url)
        return redirect("predictor:home")
    return render(request, "predictor/login.html", {"form": form})


@login_required
def account(request):
    return render(request, "predictor/account.html", {
        "prediction_count": Prediction.objects.filter(owner=request.user).count(),
    })


def dashboard(request):
    meta, _ = _meta_or_none()
    counts = {r["predicted_label"]: r["n"]
              for r in Prediction.objects.values("predicted_label").annotate(n=Count("id"))}
    avgs = Prediction.objects.aggregate(d=Avg("prob_dropout"), e=Avg("prob_enrolled"), g=Avg("prob_graduate"))
    high_risk = sum(1 for p in Prediction.objects.only("prob_dropout") if p.prob_dropout >= 0.5)
    return render(request, "predictor/dashboard.html", {
        "meta": meta,
        "total": Prediction.objects.count(),
        "high_risk": high_risk,
        "avg_dropout": (avgs["d"] or 0) * 100,
        "pred_counts": {k: counts.get(k, 0) for k in ("Dropout", "Enrolled", "Graduate")},
        "recent": Prediction.objects.all()[:6],
        "class_dist": meta["class_distribution"] if meta else {},
        "importance": dict(list(meta["feature_importance"].items())[:10]) if meta else {},
    })


def model_info(request):
    meta, error = _meta_or_none()
    fig_dir = Path(__file__).resolve().parent / "static" / "predictor" / "figures"
    figures = [(f"predictor/figures/{n}", c) for n, c in FIGURE_CAPTIONS.items() if (fig_dir / n).exists()]
    return render(request, "predictor/model_info.html", {
        "meta": meta, "model_error": error, "comparison": ml.load_comparison(), "figures": figures,
        "importance": meta["feature_importance"] if meta else {},
    })
