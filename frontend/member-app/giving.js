if (VinyrdClient.requireSession()) {
  const qs = (selector) => document.querySelector(selector);
  let toastTimer;

  const showToast = (message) => {
    const toast = qs("#statusToast");
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2200);
  };

  const labelize = (value) =>
    String(value || "")
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());

  const money = (amount, currency = "TZS") =>
    Number(amount || 0).toLocaleString(undefined, {maximumFractionDigits: 0}) + " " + currency;

  const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);

  const formatDate = (value) => {
    if (!value) return "Date unavailable";
    return new Intl.DateTimeFormat(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(new Date(value));
  };

  const renderGiving = (giving) => {
    const latest = giving && giving.latest ? giving.latest : [];
    qs("#givingTotal").textContent = money(giving && giving.total_amount, giving && giving.currency || "TZS");
    qs("#givingCount").textContent = String(latest.length);

    qs("#givingList").innerHTML = latest.length
      ? latest.map((item) => {
          const meta = [
            labelize(item.payment_method || "recorded"),
            item.reference_code ? "Ref " + item.reference_code : null,
            formatDate(item.received_at),
          ].filter(Boolean).join(" • ");

          return '<div class="giving-row">' +
            '<div class="giving-row-icon"><img src="./assets/icon-giving.svg" alt=""></div>' +
            '<div class="giving-row-copy"><strong>' + escapeHtml(labelize(item.type)) + '</strong><span>' + escapeHtml(meta) + '</span></div>' +
            '<strong class="giving-row-amount">' + escapeHtml(money(item.amount, item.currency)) + '</strong>' +
          '</div>';
        }).join("")
      : '<div class="giving-empty">No giving entries found yet.</div>';
  };

  const loadGiving = async () => {
    try {
      const data = await VinyrdClient.apiRequest("/member-portal/me");
      renderGiving(data.giving || {});
    } catch (error) {
      if (error.status === 403) {
        window.location.replace("./home.html");
        return;
      }
      if (error.status === 401) {
        VinyrdClient.clearSession();
        window.location.replace("./login.html");
        return;
      }
      showToast("Could not load your giving history.");
    }
  };

  const openForm = () => {
    qs("#givingFormCard").hidden = false;
    qs("#givingSuccess").textContent = "";
    qs("#givingFormCard").scrollIntoView({behavior: "smooth", block: "start"});
  };

  const closeForm = () => {
    qs("#givingFormCard").hidden = true;
  };

  qs("#openGivingForm").addEventListener("click", openForm);
  qs("#closeGivingForm").addEventListener("click", closeForm);

  document.querySelectorAll("[data-amount]").forEach((button) => {
    button.addEventListener("click", () => {
      qs("#givingAmount").value = button.dataset.amount;
    });
  });

  qs("#givingForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = qs("#submitGiving");
    const values = new FormData(form);

    submit.disabled = true;
    submit.textContent = "Recording...";

    try {
      const created = await VinyrdClient.apiRequest("/member-portal/giving", {
        method: "POST",
        body: JSON.stringify({
          contribution_type: String(values.get("contribution_type") || ""),
          amount: String(values.get("amount") || ""),
          currency: "TZS",
          payment_method: String(values.get("payment_method") || ""),
          reference_code: String(values.get("reference_code") || "").trim() || null,
          notes: String(values.get("notes") || "").trim() || null,
        }),
      });

      form.reset();
      qs("#givingSuccess").textContent =
        "Recorded " + money(created.amount, created.currency) + " as " + labelize(created.type) + ".";
      closeForm();
      await loadGiving();
      showToast("Giving entry recorded.");
    } catch (error) {
      showToast(error.message || "Could not record giving.");
    } finally {
      submit.disabled = false;
      submit.textContent = "Record giving";
    }
  });

  document.querySelectorAll("[data-route]").forEach((control) => {
    control.addEventListener("click", (event) => {
      event.preventDefault();
      const route = control.dataset.route;
      showToast(route.charAt(0).toUpperCase() + route.slice(1) + " is the next Vinyrd screen.");
    });
  });

  loadGiving();
}
