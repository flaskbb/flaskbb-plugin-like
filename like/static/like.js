(function () {
  "use strict";

  function patchCounts(counts) {
    for (const entry of counts) {
      const blocks = document.querySelectorAll(
        `.like-counts[data-user-id="${entry.user_id}"]`
      );
      for (const block of blocks) {
        block.querySelector(".like-counts-given").textContent = entry.given;
        block.querySelector(".like-counts-received").textContent =
          entry.received;
      }
    }
  }

  // Delegated, because the widget this fires on is replaced by the response
  // of the request it just sent.
  document.addEventListener("submit", async (event) => {
    const form = event.target.closest("form[data-like-form]");
    if (!form) {
      return;
    }
    event.preventDefault();

    const widget = form.closest(".like-widget");
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;

    let response;
    try {
      response = await fetch(form.action, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        // Carries the form's CSRF token, so the view's LikeActionForm
        // validates exactly like it does for a plain post.
        body: new FormData(form),
      });
    } catch (error) {
      // Offline or the request never landed - nothing changed server side,
      // so let the user try again.
      button.disabled = false;
      return;
    }

    if (!response.ok) {
      // A stale token, or the post was liked/unliked from somewhere else in
      // the meantime. Submit for real so the user lands on the same page the
      // no-JS flow would have given them.
      form.submit();
      return;
    }

    const data = await response.json();
    widget.outerHTML = data.widget;
    patchCounts(data.counts);
  });
})();
