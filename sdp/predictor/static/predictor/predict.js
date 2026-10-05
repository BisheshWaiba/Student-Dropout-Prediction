(function () {
  "use strict";

  var form = document.querySelector("[data-predict-form]");
  if (!form) return;

  // Completion count. Required fields carry the `required` attribute; the optional student ref does not.
  var required = form.querySelectorAll("[required]");
  var progress = form.querySelector("[data-progress]");
  var count = form.querySelector("[data-progress-count]");
  var bar = form.querySelector("[data-progress-bar]");

  function update() {
    var done = 0;
    required.forEach(function (field) {
      if (field.value.trim() !== "") done++;
    });
    count.textContent = done;
    bar.style.transform = "scaleX(" + (required.length ? done / required.length : 0) + ")";
  }

  progress.hidden = false; // ships hidden so the page works without JS
  form.addEventListener("input", update);
  form.addEventListener("change", update);
  update();

  // After a failed submit, jump to the first field that needs attention.
  var invalid = form.querySelector('[aria-invalid="true"]');
  if (invalid) invalid.focus();

  // Hold the button while the request is in flight so a double click can't save two predictions.
  var submit = form.querySelector("[type=submit]");
  var spinner = submit.querySelector(".spinner-border");
  var icon = submit.querySelector(".bi");
  var label = submit.querySelector("[data-submit-label]");

  function setBusy(busy) {
    submit.disabled = busy;
    spinner.hidden = !busy;
    icon.hidden = busy;
    label.textContent = busy ? "Predicting..." : "Predict";
    if (busy) submit.setAttribute("aria-busy", "true");
    else submit.removeAttribute("aria-busy");
  }

  form.addEventListener("submit", function () { setBusy(true); });
  // Coming back via the browser's back button restores the page from cache.
  window.addEventListener("pageshow", function (event) { if (event.persisted) setBusy(false); });
})();
