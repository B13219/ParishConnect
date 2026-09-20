if (VinyrdClient.requireSession()) {
  const qs = (selector) => document.querySelector(selector);
  let toastTimer;

  const showToast = (message) => {
    const toast = qs("#statusToast");
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2300);
  };

  const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);

  const labelize = (value) =>
    String(value || "")
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());

  const formatDate = (value) =>
    new Intl.DateTimeFormat(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(new Date(value));

  const requestCard = (prayer) => {
    const privacy = prayer.visibility === "shareable"
      ? "Shareable anonymously"
      : "Pastoral team only";

    return '<article class="prayer-request-card">' +
      '<div class="prayer-request-topline">' +
        '<div><strong>' + escapeHtml(labelize(prayer.category)) + '</strong>' +
          '<span>' + escapeHtml(formatDate(prayer.created_at)) + '</span></div>' +
        '<span class="prayer-status">' + escapeHtml(labelize(prayer.status)) + '</span>' +
      '</div>' +
      '<p>' + escapeHtml(prayer.body) + '</p>' +
      '<div class="prayer-request-meta">' +
        '<span>' + escapeHtml(privacy) + '</span>' +
        '<span>' + (prayer.allow_contact ? "Contact allowed" : "No contact requested") + '</span>' +
      '</div>' +
    '</article>';
  };

  const renderPrayers = (prayers) => {
    qs("#prayerCount").textContent = String(prayers.length);
    qs("#prayerList").innerHTML = prayers.length
      ? prayers.map(requestCard).join("")
      : '<div class="prayer-empty">You have not submitted a prayer request yet.</div>';
  };

  const loadPrayers = async () => {
    try {
      const prayers = await VinyrdClient.apiRequest("/member-portal/prayers");
      renderPrayers(prayers);
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        VinyrdClient.clearSession();
        window.location.replace("./login.html");
        return;
      }
      showToast("Could not load your prayer requests.");
    }
  };

  qs("#prayerForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = qs("#submitPrayer");
    const data = new FormData(form);

    submit.disabled = true;
    submit.textContent = "Submitting...";

    try {
      await VinyrdClient.apiRequest("/member-portal/prayers", {
        method: "POST",
        body: JSON.stringify({
          category: String(data.get("category") || "general"),
          body: String(data.get("body") || "").trim(),
          visibility: String(data.get("visibility") || "pastoral_team"),
          allow_contact: data.get("allow_contact") === "on",
        }),
      });

      form.reset();
      form.querySelector('[name="allow_contact"]').checked = true;
      showToast("Prayer request submitted.");
      await loadPrayers();
    } catch (error) {
      showToast(error.message || "Could not submit your prayer request.");
    } finally {
      submit.disabled = false;
      submit.textContent = "Submit prayer request";
    }
  });

  loadPrayers();
}
