const API_BASE = "http://127.0.0.1:8003/api/v1";

const fetchJson = async (path) => {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
};

const sendJson = async (path, method, payload) => {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `${path} returned ${response.status}`);
  }
  return response.json();
};

const formPayload = (form) =>
  Object.fromEntries(
    Array.from(new FormData(form).entries()).map(([key, value]) => [
      key,
      typeof value === "string" && value.trim() === "" ? null : value,
    ]),
  );

const formatCurrency = (amount, currency = "TZS") =>
  `${Number(amount || 0).toLocaleString()} ${currency}`;

const formatDateTime = (value) => (value ? new Date(value).toLocaleString() : "Not set");

const labelize = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const emptyState = (message) => `<div class="empty-state">${message}</div>`;

const row = ({ title, subtitle, tag, tone = "" }) => `
  <div class="row">
    <div>
      <strong>${title}</strong>
      <span>${subtitle}</span>
    </div>
    <div class="row-actions">
      <span class="tag ${tone}">${tag}</span>
    </div>
  </div>
`;

const setStatus = (message, kind = "") => {
  const el = document.querySelector("#memberPortalStatus");
  el.textContent = message;
  el.className = `status-pill ${kind}`.trim();
};

const renderPortal = (data) => {
  const profile = data.profile;
  document.querySelector("#memberName").textContent = profile.name;
  document.querySelector("#memberContact").textContent = [
    profile.phone || "No phone",
    profile.email || "No email",
  ].join(" - ");
  document.querySelector("#memberProfileDetails").innerHTML = [
    row({
      title: profile.name,
      subtitle: [profile.phone || "No phone", profile.email || "No email"].join(" - "),
      tag: labelize(profile.status),
      tone: profile.status === "active" ? "green" : "muted",
    }),
  ].join("");

  const householdPeople = data.household?.people || [];
  document.querySelector("#memberHousehold").innerHTML =
    householdPeople
      .map((person) =>
        row({
          title: person.name,
          subtitle: labelize(person.relationship),
          tag: person.can_self_check_in ? "self" : "assisted",
          tone: person.can_self_check_in ? "green" : "muted",
        }),
      )
      .join("") || emptyState("No household dependents linked yet.");

  document.querySelector("#memberEvents").innerHTML =
    data.events
      .map((event) =>
        row({
          title: event.name,
          subtitle: `${formatDateTime(event.starts_at)} - ${event.location || "No location"}`,
          tag: labelize(event.type),
          tone: "green",
        }),
      )
      .join("") || emptyState("No upcoming events found.");

  document.querySelector("#memberMessages").innerHTML =
    data.messages
      .map((message) =>
        row({
          title: message.subject || "Announcement",
          subtitle: message.body,
          tag: message.channel.toUpperCase(),
          tone: message.status === "sent" ? "green" : "amber",
        }),
      )
      .join("") || emptyState("No messages found.");

  document.querySelector("#memberGivingTotal").textContent = formatCurrency(
    data.giving.total_amount,
    data.giving.currency,
  );
  document.querySelector("#memberGiving").innerHTML =
    data.giving.latest
      .map((contribution) =>
        row({
          title: `${labelize(contribution.type)} - ${formatCurrency(
            contribution.amount,
            contribution.currency,
          )}`,
          subtitle: [
            labelize(contribution.payment_method || "cash"),
            contribution.reference_code ? `Ref: ${contribution.reference_code}` : null,
            formatDateTime(contribution.received_at),
          ]
            .filter(Boolean)
            .join(" - "),
          tag: contribution.currency,
          tone: "green",
        }),
      )
      .join("") || emptyState("No giving receipts found.");
};

const submitMemberGiving = async (form) => {
  const payload = formPayload(form);
  payload.amount = Number(payload.amount || 0);

  try {
    setStatus("Submitting");
    const contribution = await sendJson("/member-portal/giving", "POST", payload);
    form.reset();
    form.elements.currency.value = "TZS";
    document.querySelector("#memberGivingReceipt").innerHTML = `
      <strong>Thank you. ${formatCurrency(contribution.amount, contribution.currency)} recorded.</strong>
      <span>${contribution.reference_code ? `Ref: ${contribution.reference_code}` : labelize(contribution.payment_method)}</span>
    `;
    await loadPortal();
    setStatus("Giving recorded", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Giving failed", "error");
  }
};

const loadPortal = async () => {
  try {
    setStatus("Loading");
    const data = await fetchJson("/member-portal/me");
    renderPortal(data);
    setStatus("Connected", "ok");
  } catch (error) {
    console.error(error);
    setStatus("Offline", "error");
  }
};

document.querySelector("#memberGivingForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitMemberGiving(event.currentTarget);
});

document.querySelectorAll("[data-member-amount]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelector("#memberGivingAmount").value = button.dataset.memberAmount;
  });
});

loadPortal();
