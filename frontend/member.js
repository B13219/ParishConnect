const API_BASE = "http://127.0.0.1:8003/api/v1";
let portalData = null;

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

  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = body.detail;

    if (typeof detail === "object" && detail !== null) {
      const error = new Error(detail.reason || `Request failed with ${response.status}`);
      error.details = detail;
      error.status = response.status;
      throw error;
    }

    throw new Error(detail || `${path} returned ${response.status}`);
  }

  return body;
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

const setLocationStatus = (message, kind = "") => {
  const element = document.querySelector("#memberLocationStatus");

  if (!element) {
    return;
  }

  element.className = `receipt-panel ${kind}`.trim();
  element.innerHTML = message;
};

const locationErrorMessage = (error) => {
  if (error.details?.reason === "outside_geofence") {
    return `
      <strong>You are outside the attendance area.</strong>
      <span>
        Distance: ${error.details.distance_meters} metres.
        Allowed radius: ${error.details.allowed_radius_meters} metres.
      </span>
    `;
  }

  if (error.code === 1) {
    return `
      <strong>Location permission was denied.</strong>
      <span>Allow location access in your browser and try again.</span>
    `;
  }

  if (error.code === 2) {
    return `
      <strong>Your location could not be determined.</strong>
      <span>Turn on GPS or location services and try again.</span>
    `;
  }

  if (error.code === 3) {
    return `
      <strong>Location request timed out.</strong>
      <span>Move somewhere with a clearer GPS signal and retry.</span>
    `;
  }

  return `
    <strong>Location check-in failed.</strong>
    <span>${error.message || "Please try again."}</span>
  `;
};

const getMemberGpsPosition = () =>
  new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Location services are not supported by this browser."));
      return;
    }

    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 0,
    });
  });

const checkInWithLocation = async (eventId, button) => {
  if (!portalData?.profile?.id) {
    setLocationStatus(
      `
        <strong>Member profile unavailable.</strong>
        <span>Reload the page and try again.</span>
      `,
      "error",
    );
    return;
  }

  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Finding location...";

  setLocationStatus(`
    <strong>Checking your location...</strong>
    <span>Please allow ParishConnect to access your device location.</span>
  `);

  try {
    const position = await getMemberGpsPosition();
    const { latitude, longitude, accuracy } = position.coords;

    button.textContent = "Confirming attendance...";

    const attendance = await sendJson(
      "/attendance/geofence-check-ins",
      "POST",
      {
        event_id: eventId,
        person_type: "member",
        person_id: portalData.profile.id,
        latitude,
        longitude,
        accuracy_meters: accuracy,
      },
    );

    setLocationStatus(
      `
        <strong>Attendance confirmed.</strong>
        <span>
          You were detected ${attendance.distance_meters} metres from the church location.
        </span>
      `,
      "ok",
    );

    button.textContent = "Checked in";
    button.disabled = true;
  } catch (error) {
  console.error("Geolocation error:", {
    code: error.code,
    message: error.message,
    details: error.details,
  });

  setLocationStatus(locationErrorMessage(error), "error");
    button.disabled = false;
    button.textContent = originalText;
  }
};

const renderPortal = (data) => {
  const profile = data.profile;
  document.querySelector("#memberName").textContent = profile.name;
  document.querySelector("#memberContact").textContent = [
    profile.phone || "No phone",
    profile.email || "No email",
  ].join(" - ");
  document.querySelector("#memberEvents").innerHTML =
  data.events
    .map(
      (event) => `
        <div class="row">
          <div>
            <strong>${event.name}</strong>
            <span>
              ${formatDateTime(event.starts_at)} -
              ${event.location || "No location"}
            </span>
          </div>

          <div class="row-actions">
            <span class="tag green">${labelize(event.type)}</span>
            <button
              class="mini-button"
              type="button"
              data-location-check-in
              data-event-id="${event.id}"
            >
              Check in with location
            </button>
          </div>
        </div>
      `,
    )
    .join("") || emptyState("No upcoming events found.");

document.querySelectorAll("[data-location-check-in]").forEach((button) => {
  button.addEventListener("click", () => {
    checkInWithLocation(button.dataset.eventId, button);
  });
});

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
    portalData = data;
    renderPortal(data);
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
