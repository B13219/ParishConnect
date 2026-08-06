const API_BASE = "http://127.0.0.1:8003/api/v1";

const params = new URLSearchParams(window.location.search);
const eventId = params.get("event_id");
const qrToken = params.get("token");

const state = {
  people: null,
  households: null,
  eventToken: null,
};

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

const setScanStatus = (message, kind = "") => {
  const el = document.querySelector("#scanStatus");
  el.textContent = message;
  el.className = `scan-status ${kind}`.trim();
};

const formatDateTime = (value) => (value ? new Date(value).toLocaleString() : "Not set");

const householdPeople = () =>
  (state.households?.households || []).flatMap((household) =>
    household.people
      .filter((person) => person.person_type === "child" || person.person_type === "dependent")
      .map((person) => ({
        id: person.id,
        name: `${person.name} - ${household.name}`,
      })),
  );

const renderPeople = () => {
  const type = document.querySelector("#scanPersonType").value;
  const select = document.querySelector("#scanPersonSelect");
  const people =
    type === "member"
      ? state.people.members.filter((member) => member.status === "active")
      : type === "visitor"
      ? state.people.visitors.filter((visitor) => visitor.follow_up_status !== "converted")
      : householdPeople();

  select.innerHTML =
    people.map((person) => `<option value="${person.id}">${person.name}</option>`).join("") ||
    '<option value="">No records available</option>';
};

const loadScanPage = async () => {
  if (!eventId || !qrToken) {
    setScanStatus("This QR link is missing check-in details.", "error");
    return;
  }

  try {
    setScanStatus("Loading records");
    const [people, households, tokenData] = await Promise.all([
      fetchJson("/members/"),
      fetchJson("/members/households"),
      fetchJson(`/attendance/events/${eventId}/qr-token`),
    ]);
    state.people = people;
    state.households = households;
    state.eventToken = tokenData;
    document.querySelector("#scanEventName").textContent = tokenData.event.name;
    document.querySelector("#scanWindow").textContent = `${formatDateTime(
      tokenData.opens_at,
    )} to ${formatDateTime(tokenData.closes_at)}`;
    renderPeople();
    setScanStatus(tokenData.active ? "Ready for check-in" : "QR window is not open yet");
  } catch (error) {
    console.error(error);
    setScanStatus(error.message || "Unable to prepare check-in", "error");
  }
};

const submitScanCheckIn = async (form) => {
  const payload = {
    event_id: eventId,
    qr_token: qrToken,
    person_type: form.elements.person_type.value,
    person_id: form.elements.person_id.value,
  };

  try {
    setScanStatus("Checking in");
    const record = await sendJson("/attendance/qr-check-ins", "POST", payload);
    setScanStatus(`${record.person_name} checked in for ${record.event_name}`, "ok");
  } catch (error) {
    console.error(error);
    setScanStatus(error.message || "Check-in failed", "error");
  }
};

document.querySelector("#scanPersonType").addEventListener("change", renderPeople);
document.querySelector("#scanCheckInForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitScanCheckIn(event.currentTarget);
});

loadScanPage();
