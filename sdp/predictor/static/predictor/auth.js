(function () {
  "use strict";

  // Show/hide password. The buttons ship hidden so the page works without JS.
  document.querySelectorAll("[data-reveal]").forEach(function (button) {
    var input = document.getElementById(button.dataset.reveal);
    if (!input) return;
    button.hidden = false;
    button.addEventListener("click", function () {
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      button.setAttribute("aria-pressed", String(show));
      button.setAttribute("aria-label", show ? "Hide password" : "Show password");
      button.firstElementChild.className = show ? "bi bi-eye-slash" : "bi bi-eye";
    });
  });

  // Hold the submit button while the request is in flight to prevent double submits.
  var form = document.querySelector("[data-auth-form]");
  if (!form) return;
  var submit = form.querySelector("[type=submit]");
  var spinner = submit.querySelector(".spinner-border");

  function setBusy(busy) {
    submit.disabled = busy;
    spinner.hidden = !busy;
    if (busy) submit.setAttribute("aria-busy", "true");
    else submit.removeAttribute("aria-busy");
  }

  form.addEventListener("submit", function () { setBusy(true); });
  // Coming back via the browser's back button restores the page from cache.
  window.addEventListener("pageshow", function (event) { if (event.persisted) setBusy(false); });
})();
