(function () {
  "use strict";

  document.addEventListener("click", function (event) {
    var target = event.target.closest("[data-confirm]");
    if (!target) return;
    var message = target.getAttribute("data-confirm") || "Are you sure?";
    if (!window.confirm(message)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  });

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-copy]");
    if (!trigger) return;
    var selector = trigger.getAttribute("data-copy");
    var source = document.querySelector(selector);
    if (!source) return;
    var text = source.value !== undefined ? source.value : source.textContent;
    if (!navigator.clipboard) {
      window.prompt("Copy the text below", text);
      return;
    }
    navigator.clipboard.writeText(text).then(function () {
      var original = trigger.textContent;
      trigger.textContent = "Copied";
      setTimeout(function () {
        trigger.textContent = original;
      }, 1500);
    });
  });

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-print]");
    if (!trigger) return;
    event.preventDefault();
    window.print();
  });

  document.querySelectorAll("form[data-dirty-check]").forEach(function (form) {
    var dirty = false;
    form.addEventListener("input", function () {
      dirty = true;
    });
    form.addEventListener("submit", function () {
      dirty = false;
    });
    window.addEventListener("beforeunload", function (event) {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    });
  });
})();
