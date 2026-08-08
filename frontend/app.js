const API_BASE = "http://127.0.0.1:8004/api/v1";

const state = {
  auth: JSON.parse(localStorage.getItem("parishconnect_auth") || "null"),
  people: null,
  attendance: null,
  serviceTemplates: null,
  geofence: null,
  households: null,
  messages: null,
  messageRecipients: null,
  stewardship: null,
  reports: null,
  admin: null,
  backupManifest: null,
  importPreview: null,
  peopleFilters: {
    query: "",
    memberStatus: "all",
    visitorStatus: "all",
  },
};
let geofenceMap = null;
let geofenceMarker = null;
let geofenceCircle = null;

const sections = [
  "people",
  "imports",
  "attendance",
  "settings",
  "households",
  "messages",
  "stewardship",
  "reports",
  "admin",
];
const navSections = [
  "overview",
  "people",
  "imports",
  "attendance",
  "settings",
  "households",
  "messages",
  "stewardship",
  "reports",
  "admin",
];

const formatCurrency = (amount, currency = "TZS") =>
  `${Number(amount || 0).toLocaleString()} ${currency}`;

const formatDateTime = (value) => (value ? new Date(value).toLocaleString() : "Not set");

const labelize = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const rolePermissions = {
  administrator: [
    "people",
    "imports",
    "attendance",
    "households",
    "messages",
    "stewardship",
    "reports",
    "settings",
    "admin",
  ],
  pastor_leader: ["people", "messages", "stewardship", "reports","settings"],
  accountant: ["stewardship", "reports"],
  receptionist: ["people", "imports", "attendance", "households"],
  usher: ["attendance"],
};

const currentRoles = () => state.auth?.user?.roles || [];

const canUseSection = (section) =>
  currentRoles().includes("administrator") ||
  currentRoles().some((role) => (rolePermissions[role] || []).includes(section));

const permittedSections = () => (state.auth?.access_token ? sections.filter(canUseSection) : []);

const authHeaders = () =>
  state.auth?.access_token ? { Authorization: `Bearer ${state.auth.access_token}` } : {};

const messageTemplates = {
  sunday_reminder: {
    subject: "Sunday Service Reminder",
    body: "Reminder: Sunday service starts at 9:00 AM. We look forward to worshipping together.",
  },
  event_reminder: {
    subject: "Event Reminder",
    body: "Reminder: our upcoming church event is approaching. Please check the event details and join us.",
  },
  visitor_follow_up: {
    subject: "Thank You For Visiting",
    body: "Thank you for worshipping with us. We were blessed to have you and would love to see you again.",
  },
  giving_reminder: {
    subject: "Giving Reminder",
    body: "Thank you for your faithful giving. You may give during service or through the available giving options.",
  },
  urgent_notice: {
    subject: "Important Church Notice",
    body: "Important notice from church leadership. Please read this update and share with your household.",
  },
};

const toggleServiceDayAttendance = async () => {
  const event = getServiceDayEvent();

  if (!event) {
    setStatus("No service scheduled for today", "error");
    return;
  }

  const action =
    event.attendance_status === "open"
      ? "close"
      : "open";

  try {
    setBusy(true);

    setStatus(
      action === "open"
        ? "Opening attendance"
        : "Closing attendance",
    );

    await sendJson(
      `/attendance/events/${event.id}/${action}`,
      "POST",
    );

    await loadSection("attendance");

    setStatus(
      action === "open"
        ? "Attendance opened"
        : "Attendance closed",
      "ok",
    );
  } catch (error) {
    console.error(error);

    setStatus(
      error.message || "Attendance status could not be changed",
      "error",
    );
  } finally {
    setBusy(false);
  }
};

const generateRecurringServices = async () => {
  try {
    setBusy(true);
    setStatus("Generating upcoming services");

    const result = await sendJson(
      "/attendance/service-templates/generate",
      "POST",
    );

    await loadSection("attendance");

    if (result.created > 0) {
      setStatus(
        `${result.created} upcoming service${
          result.created === 1 ? "" : "s"
        } generated`,
        "ok",
      );
    } else {
      setStatus(
        `${result.skipped || 0} service${
          result.skipped === 1 ? "" : "s"
        } already scheduled`,
        "ok",
      );
    }
  } catch (error) {
    console.error(error);

    setStatus(
      error.message || "Upcoming services could not be generated",
      "error",
    );
  } finally {
    setBusy(false);
  }
};

const setStatus = (text, kind = "") => {
  const el = document.querySelector("#connectionStatus");
  const loginEl = document.querySelector("#loginStatus");
  [el, loginEl].forEach((statusEl) => {
    if (!statusEl) {
      return;
    }
    statusEl.textContent = text;
    statusEl.className = `status-pill ${kind}`.trim();
  });
};

const setBusy = (busy) => {
  document.querySelectorAll("button").forEach((button) => {
    button.disabled =
      busy ||
      (button.id === "commitImport" &&
        (!state.importPreview || Number(state.importPreview.valid_rows || 0) === 0));
  });
};

const fetchJson = async (path) => {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
};

const fetchText = async (path) => {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.text();
};
const sendJson = async (path, method, payload = null) => {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: payload ? JSON.stringify(payload) : null,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `${path} returned ${response.status}`);
  }

  if (response.status === 204) {
    return null;
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

const emptyState = (message) => `<div class="empty-state">${message}</div>`;

const setSkeletons = () => {
  [
    "#memberList",
    "#visitorList",
    "#importPreviewList",
    "#eventList",
    "#serviceTemplateList",
    "#checkInList",
    "#householdList",
    "#contributionBreakdown",
    "#messageList",
    "#messageRecipientList",
    "#contributionList",
    "#reportMetrics",
    "#reportAttendance",
    "#reportStewardship",
    "#reportObservations",
    "#adminRoleList",
    "#adminUserList",
    "#auditLogList",
    "#branchSettingsSummary",
    "#backupManifestSummary",
  ].forEach((selector) => {
    document.querySelector(selector).innerHTML =
      '<div class="skeleton"></div><div class="skeleton"></div>';
  });
};

const row = ({ title, subtitle, tag, tone = "", action = "" }) => `
  <div class="row">
    <div>
      <strong>${title}</strong>
      <span>${subtitle}</span>
    </div>
    <div class="row-actions">
      <span class="tag ${tone}">${tag}</span>
      ${action}
    </div>
  </div>
`;

const applyRoleAccess = () => {
  const hasLogin = Boolean(state.auth?.access_token);
  const roles = currentRoles();
  document.querySelector("#loginScreen").hidden = hasLogin;
  document.querySelector("#appShell").hidden = !hasLogin;
  document.querySelector("#authSummary").textContent = hasLogin
    ? `${state.auth.user.name} - ${roles.map(labelize).join(", ")}`
    : "Guest mode";
  document.querySelector("#logoutButton").hidden = !hasLogin;
  const permissionNote = document.querySelector("#permissionNote");
  if (permissionNote) {
    permissionNote.textContent = hasLogin
      ? "Role-aware controls are active for this admin session."
      : "Login to preview role boundaries for admin, pastor, receptionist, and usher users.";
  }

  document.querySelectorAll("[data-section-link]").forEach((link) => {
    const section = link.dataset.sectionLink;
    const isHidden = section !== "overview" && hasLogin && !canUseSection(section);
    link.hidden = isHidden;
    link.classList.remove("restricted");
    link.title = "";
  });

  sections.forEach((section) => {
    const panel = document.getElementById(section);
    if (panel) {
      panel.hidden = hasLogin && !canUseSection(section);
    }
  });

  const currentHash = window.location.hash.replace("#", "");
  if (currentHash && currentHash !== "overview" && hasLogin && !canUseSection(currentHash)) {
    window.location.hash = "overview";
    setActiveNav("overview");
  }
};

const personMatchesQuery = (person, query) => {
  if (!query) {
    return true;
  }
  const haystack = [
    person.name,
    person.first_name,
    person.last_name,
    person.phone,
    person.email,
    person.status,
    person.follow_up_status,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query.toLowerCase());
};

const memberLifecycleActions = (member) => {
  if (["transferred", "deceased", "discontinued"].includes(member.status)) {
    return "";
  }

  return `
    <button class="mini-button" data-member-status="${member.id}:transferred" type="button">Transfer</button>
    <button class="mini-button danger" data-member-status="${member.id}:deceased" type="button">Deceased</button>
    <button class="mini-button muted" data-member-status="${member.id}:discontinued" type="button">Discontinue</button>
  `;
};

const renderPeople = () => {
  const allMembers = state.people?.members || [];
  const allVisitors = state.people?.visitors || [];
  const members = allMembers.filter(
    (member) =>
      personMatchesQuery(member, state.peopleFilters.query) &&
      (state.peopleFilters.memberStatus === "all" ||
        member.status === state.peopleFilters.memberStatus),
  );
  const visitors = allVisitors.filter(
    (visitor) =>
      personMatchesQuery(visitor, state.peopleFilters.query) &&
      (state.peopleFilters.visitorStatus === "all" ||
        visitor.follow_up_status === state.peopleFilters.visitorStatus),
  );

  document.querySelector("#memberCount").textContent = allMembers.length;
  document.querySelector("#visitorCount").textContent = allVisitors.length;
  document.querySelector("#memberList").innerHTML =
    members
      .map((member) =>
        row({
          title: member.name,
          subtitle: [member.phone || "No phone", member.email || "No email"].join(" - "),
          tag: member.status,
          tone: member.status === "active" ? "green" : "muted",
          action: `
            <button class="mini-button" data-edit-member="${member.id}" type="button">Edit</button>
            ${memberLifecycleActions(member)}
          `,
        }),
      )
      .join("") || emptyState("No members found.");
  document.querySelector("#visitorList").innerHTML =
    visitors
      .map((visitor) =>
        row({
          title: visitor.name,
          subtitle: [visitor.phone || "No phone", visitor.email || "No email"].join(" - "),
          tag: visitor.follow_up_status,
          tone: "amber",
          action: `
            <button class="mini-button" data-edit-visitor="${visitor.id}" type="button">Edit</button>
            ${
              visitor.converted_member_id
                ? ""
                : `<button class="mini-button" data-convert-visitor="${visitor.id}" type="button">Convert</button>`
            }
          `,
        }),
      )
      .join("") || emptyState("No visitors found.");

  document.querySelectorAll("[data-edit-member]").forEach((button) => {
    button.addEventListener("click", () => openPersonDialog("member", button.dataset.editMember));
  });
  document.querySelectorAll("[data-edit-visitor]").forEach((button) => {
    button.addEventListener("click", () => openPersonDialog("visitor", button.dataset.editVisitor));
  });
  document.querySelectorAll("[data-convert-visitor]").forEach((button) => {
    button.addEventListener("click", () => convertVisitor(button.dataset.convertVisitor));
  });
  document.querySelectorAll("[data-member-status]").forEach((button) => {
    button.addEventListener("click", () => {
      const [memberId, lifecycleStatus] = button.dataset.memberStatus.split(":");
      updateMemberStatus(memberId, lifecycleStatus);
    });
  });
  renderCheckInPersonOptions();
  renderHouseholdMemberOptions();
  renderContributionMemberOptions();
  applyRoleAccess();
};

const renderImportPreview = () => {
  const preview = state.importPreview;
  const rows = preview?.rows || [];
  document.querySelector("#importSummary").textContent = preview
    ? `${preview.total_rows} rows checked - ${preview.failed_rows} need attention`
    : "No preview yet";
  document.querySelector("#importValidCount").textContent = `${preview?.valid_rows || 0} valid`;
  document.querySelector("#commitImport").disabled = !preview || preview.valid_rows === 0;
  document.querySelector("#importPreviewList").innerHTML =
    rows
      .map((item) =>
        row({
          title: `Row ${item.row_number}: ${item.data.first_name || ""} ${
            item.data.last_name || ""
          }`.trim(),
          subtitle:
            item.status === "valid"
              ? [item.data.phone || "No phone", item.data.email || "No email"].join(" - ")
              : item.errors.join(" - "),
          tag: item.status,
          tone: item.status === "valid" ? "green" : "amber",
        }),
      )
      .join("") || emptyState("Preview rows will appear here.");
};
const getServiceDayEvent = () => {
  const events = state.attendance?.events || [];
  const now = new Date();

  const todaysEvents = events.filter((event) => {
    if (!event.starts_at) {
      return false;
    }

    const startsAt = new Date(event.starts_at);

    return (
      startsAt.getFullYear() === now.getFullYear() &&
      startsAt.getMonth() === now.getMonth() &&
      startsAt.getDate() === now.getDate()
    );
  });

  if (!todaysEvents.length) {
    return null;
  }

  // If one service already has attendance open, always show that one.
  const openEvent = todaysEvents.find(
    (event) => event.attendance_status === "open",
  );

  if (openEvent) {
    return openEvent;
  }

  // Otherwise show the service closest to the current time.
  return todaysEvents.sort((a, b) => {
    const aDifference = Math.abs(
      new Date(a.starts_at).getTime() - now.getTime(),
    );

    const bDifference = Math.abs(
      new Date(b.starts_at).getTime() - now.getTime(),
    );

    return aDifference - bDifference;
  })[0];
};

const renderServiceDay = () => {
  const event = getServiceDayEvent();

  const title = document.querySelector("#serviceDayTitle");
  const meta = document.querySelector("#serviceDayMeta");
  const status = document.querySelector("#serviceDayStatus");
  const count = document.querySelector("#serviceDayCheckInCount");
  const qrStatus = document.querySelector("#serviceDayQrStatus");
  const showQrButton = document.querySelector("#serviceDayShowQr");
  const toggleButton = document.querySelector("#serviceDayToggleAttendance");
  const recentList = document.querySelector("#serviceDayRecentCheckIns");

  if (!event) {
    title.textContent = "No active service";
    meta.textContent = "No service is scheduled for today.";
    status.textContent = "No session";
    status.className = "tag muted";
    count.textContent = "0";
    qrStatus.textContent = "Closed";
    showQrButton.disabled = true;
    toggleButton.disabled = true;
    recentList.innerHTML = emptyState("No service-day check-ins yet.");
    return;
  }

  title.textContent = event.name;

  meta.textContent = [
    formatDateTime(event.starts_at),
    event.location || "No location",
  ].join(" - ");

  count.textContent = event.check_ins || 0;

 qrStatus.textContent = event.qr_active ? "Open" : "Closed";

const attendanceOpen = event.attendance_status === "open";

status.textContent =
  event.attendance_status === "closed"
    ? "Attendance closed"
    : attendanceOpen
      ? "Attendance open"
      : "Scheduled";

status.className = `tag ${attendanceOpen ? "green" : "muted"}`;

showQrButton.disabled = false;
showQrButton.dataset.eventId = event.id;

toggleButton.disabled = false;
toggleButton.dataset.eventId = event.id;

toggleButton.textContent = attendanceOpen
  ? "Close Attendance"
  : "Open Attendance";
  const recentCheckIns = (state.attendance?.recent_check_ins || []).filter(
    (checkIn) => checkIn.event_id === event.id,
  );

  recentList.innerHTML =
    recentCheckIns
      .slice(0, 5)
      .map((checkIn) =>
        row({
          title: checkIn.person_name,
          subtitle: formatDateTime(checkIn.checked_in_at),
          tag: checkIn.person_type,
          tone: checkIn.check_in_method === "qr" ? "green" : "amber",
        }),
      )
      .join("") || emptyState("No check-ins for today's service yet.");
};

const renderAttendance = () => {
  const events = state.attendance?.events || [];
  const recentCheckIns = state.attendance?.recent_check_ins || [];
  const serviceTemplates = state.serviceTemplates || [];

  document.querySelector("#checkInCount").textContent = state.attendance?.total_check_ins || 0;
  const dayNames = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

document.querySelector("#serviceTemplateList").innerHTML =
  serviceTemplates
    .map((template) =>
      row({
        title: template.name,
        subtitle: `${dayNames[template.day_of_week]} · ${
          template.start_time
        }${template.end_time ? `–${template.end_time}` : ""} · ${
          template.location || "No location"
        }`,
        tag: template.is_active ? "Active" : "Inactive",
        tone: template.is_active ? "green" : "muted",
        action: `
          <button
            class="mini-button"
            type="button"
            data-service-template-edit="${template.id}"
          >
            Edit
          </button>
       

          <button
            class="mini-button"
            type="button"
            data-service-template-delete="${template.id}"
          >
            Delete
          </button>
        `,
      }),
    )
    .join("") || emptyState("No recurring services configured.");
  document
  .querySelectorAll("[data-service-template-delete]")
  .forEach((button) => {
    button.addEventListener("click", () => {
      deleteServiceTemplate(
        button.dataset.serviceTemplateDelete,
      );
    });
  });
    document
  .querySelectorAll("[data-service-template-edit]")
  .forEach((button) => {
    button.addEventListener("click", () => {
      openServiceTemplateEditForm(
        button.dataset.serviceTemplateEdit,
      );
    });
  });
 
    document.querySelector("#eventList").innerHTML =
    events
      .map((event) =>
    row({
  title: event.name,
  subtitle: `${formatDateTime(event.starts_at)} - ${
    event.location || "No location"
  } - QR ${event.qr_active ? "open" : "closed"}`,
  tag: `${event.check_ins || 0} check-ins`,
  tone: event.qr_active ? "green" : "",
  action: `
    <button
      class="mini-button"
      data-event-qr="${event.id}"
      type="button"
    >
      QR
    </button>

    <button
      class="mini-button"
      data-event-edit="${event.id}"
      type="button"
    >
      Edit
    </button>

    <button
      class="mini-button"
      data-event-delete="${event.id}"
      type="button"
    >
      Delete
    </button>
  `,
})
      )
      .join("") || emptyState("No upcoming events found.");
  document.querySelector("#checkInList").innerHTML =
    recentCheckIns
      .map((checkIn) =>
        row({
          title: checkIn.person_name,
          subtitle: `${checkIn.event_name} - ${formatDateTime(checkIn.checked_in_at)}`,
          tag: checkIn.person_type,
          tone: checkIn.check_in_method === "qr" ? "green" : "amber",
        }),
      )
      .join("") || emptyState("No recent check-ins found.");
 document.querySelectorAll("[data-event-qr]").forEach((button) => {
  button.addEventListener("click", () => showQrToken(button.dataset.eventQr));
});

document.querySelectorAll("[data-event-edit]").forEach((button) => {
  button.addEventListener("click", () => {
    openEventEditForm(button.dataset.eventEdit);
  });
});

document.querySelectorAll("[data-event-delete]").forEach((button) => {
  button.addEventListener("click", () => {
    deleteEvent(button.dataset.eventDelete);
  });
});

renderServiceDay();
renderCheckInEventOptions();
applyRoleAccess();
};

const renderHouseholds = () => {
  const households = state.households?.households || [];
  document.querySelector("#householdList").innerHTML =
    households
      .map((household) =>
        row({
          title: household.name,
          subtitle: `${household.people.length} people - ${
            household.primary_contact || household.primary_phone || "No primary contact"
          }`,
          tag: "household",
          action: household.people
            .map(
              (person) =>
                `<span class="tag ${person.can_self_check_in ? "green" : "muted"}">${
                  person.name
                } (${person.relationship})</span>`,
            )
            .join(""),
        }),
      )
      .join("") || emptyState("No households found.");
  renderHouseholdOptions();
  applyRoleAccess();
};

const renderMessages = () => {
  const messages = state.messages?.messages || [];
  const delivery = state.messageRecipients;

  document.querySelector("#messageList").innerHTML =
    messages
      .map((message) =>
        row({
          title: message.subject || "Untitled message",
          subtitle: [
            message.body,
            `${labelize(message.channel)} for ${labelize(message.audience_type)}`,
            `${message.recipient_count || 0} recipients`,
            message.sent_at ? `Sent ${formatDateTime(message.sent_at)}` : null,
            message.scheduled_at ? `Scheduled ${formatDateTime(message.scheduled_at)}` : null,
          ]
            .filter(Boolean)
            .join(" - "),
          tag: message.status,
          tone: message.status === "sent" ? "green" : "amber",
          action: `
            <button class="mini-button" data-message-recipients="${message.id}" type="button">Recipients</button>
            ${
              message.status === "sent"
                ? ""
                : `<button class="mini-button" data-message-dispatch="${message.id}" type="button">Dispatch</button>`
            }
          `,
        }),
      )
      .join("") || emptyState("No messages found.");
  document.querySelector("#messageRecipientList").innerHTML = delivery
    ? [
        row({
          title: delivery.message.subject || "Untitled message",
          subtitle: `${delivery.recipients.length} recipients - ${labelize(
            delivery.message.channel,
          )}`,
          tag: labelize(delivery.message.status),
          tone: delivery.message.status === "sent" ? "green" : "amber",
        }),
        ...delivery.recipients.map((recipient) =>
          row({
            title: recipient.name,
            subtitle: [
              recipient.phone || "No phone",
              recipient.provider_reference ? `Ref: ${recipient.provider_reference}` : null,
            ]
              .filter(Boolean)
              .join(" - "),
            tag: labelize(recipient.delivery_status),
            tone: recipient.delivery_status === "delivered" ? "green" : "amber",
          }),
        ),
      ].join("")
    : emptyState("Select a message to view recipient delivery status.");
  document.querySelectorAll("[data-message-recipients]").forEach((button) => {
    button.addEventListener("click", () => showMessageRecipients(button.dataset.messageRecipients));
  });
  document.querySelectorAll("[data-message-dispatch]").forEach((button) => {
    button.addEventListener("click", () => dispatchMessage(button.dataset.messageDispatch));
  });
  applyRoleAccess();
};

const renderStewardship = () => {
  const finance = state.stewardship || {};
  const latest = finance.latest || [];
  const byType = finance.by_type || [];
  const formattedTotal = formatCurrency(finance.total_amount, finance.currency);

  document.querySelector("#contributionTotal").textContent = formattedTotal;
  document.querySelector("#financeTotal").textContent = formattedTotal;
  document.querySelector("#contributionCount").textContent = `${finance.contribution_count || 0} records`;
  document.querySelector("#contributionBreakdown").innerHTML =
    byType
      .map(
        (item) => `
          <div class="finance-chip">
            <span>${labelize(item.type)}</span>
            <strong>${formatCurrency(item.amount, item.currency)}</strong>
          </div>
        `,
      )
      .join("") || emptyState("No contribution breakdown yet.");
  document.querySelector("#contributionList").innerHTML =
    latest
      .map((contribution) =>
        row({
          title: `${contribution.type} - ${formatCurrency(
            contribution.amount,
            contribution.currency,
          )}`,
          subtitle: [
            contribution.member_name || "Anonymous / Visitor",
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
      .join("") || emptyState("No contribution records found.");
  renderContributionMemberOptions();
  applyRoleAccess();
};

const renderWeeklyReport = () => {
  const report = state.reports || {};
  const attendance = report.attendance || {};
  const stewardship = report.stewardship || {};
  const communication = report.communication || {};
  const people = report.people || {};
  const observations = report.observations || [];

  document.querySelector("#reportPeriod").textContent = report.period
    ? `${report.period.label} - ${formatDateTime(report.period.start)} to ${formatDateTime(
        report.period.end,
      )}`
    : "No reporting period available";
  document.querySelector("#reportMetrics").innerHTML = [
    { label: "Weekly attendance", value: attendance.total || 0 },
    {
      label: "Weekly giving",
      value: formatCurrency(stewardship.total_amount, stewardship.currency),
    },
    { label: "Messages", value: communication.total_messages || 0 },
    { label: "New visitors", value: people.new_visitors || 0 },
  ]
    .map(
      (metric) => `
        <div class="finance-chip">
          <span>${metric.label}</span>
          <strong>${metric.value}</strong>
        </div>
      `,
    )
    .join("");

  const attendanceRows = [
    row({
      title: "People checked in",
      subtitle: `${attendance.members || 0} members - ${attendance.visitors || 0} visitors - ${
        attendance.household_dependents || 0
      } household dependents`,
      tag: `${attendance.total || 0} total`,
      tone: "green",
    }),
    ...(attendance.by_event || []).map((event) =>
      row({
        title: event.event_name,
        subtitle: "Event attendance this week",
        tag: `${event.count} check-ins`,
      }),
    ),
    ...(attendance.by_method || []).map((method) =>
      row({
        title: labelize(method.method),
        subtitle: "Check-in method",
        tag: `${method.count} records`,
      }),
    ),
  ];
  document.querySelector("#reportAttendance").innerHTML =
    attendanceRows.join("") || emptyState("No weekly attendance data yet.");

  const stewardshipRows = [
    row({
      title: "Total giving recorded",
      subtitle: `${stewardship.count || 0} contribution records`,
      tag: formatCurrency(stewardship.total_amount, stewardship.currency),
      tone: "green",
    }),
    ...(stewardship.by_type || []).map((item) =>
      row({
        title: labelize(item.type),
        subtitle: `${item.count} records by giving type`,
        tag: formatCurrency(item.amount, stewardship.currency),
        tone: "green",
      }),
    ),
    ...(stewardship.by_payment_method || []).map((item) =>
      row({
        title: labelize(item.method),
        subtitle: `${item.count} records by payment method`,
        tag: formatCurrency(item.amount, stewardship.currency),
      }),
    ),
  ];
  document.querySelector("#reportStewardship").innerHTML =
    stewardshipRows.join("") || emptyState("No weekly stewardship data yet.");
  document.querySelector("#reportObservations").innerHTML =
    observations
      .map((observation) =>
        row({
          title: observation.title,
          subtitle: observation.detail,
          tag: labelize(observation.tone),
          tone:
            observation.tone === "good"
              ? "green"
              : observation.tone === "warn"
                ? "amber"
                : "",
        }),
      )
      .join("") || emptyState("No observations yet.");
  applyRoleAccess();
};

const setGeofenceCoordinates = (latitude, longitude, moveMap = true) => {
  const latitudeValue = Number(latitude);
  const longitudeValue = Number(longitude);

  if (
    !Number.isFinite(latitudeValue) ||
    !Number.isFinite(longitudeValue)
  ) {
    return;
  }

  document.querySelector("#geofenceLatitude").value =
    latitudeValue.toFixed(6);

  document.querySelector("#geofenceLongitude").value =
    longitudeValue.toFixed(6);

  if (geofenceMarker) {
    geofenceMarker.setLatLng([latitudeValue, longitudeValue]);
  }

  if (geofenceCircle) {
    geofenceCircle.setLatLng([latitudeValue, longitudeValue]);
  }

  if (moveMap && geofenceMap) {
    geofenceMap.setView([latitudeValue, longitudeValue], 17);
  }
};

const initializeGeofenceMap = () => {
  const mapElement = document.querySelector("#geofenceMap");

  if (!mapElement || typeof L === "undefined") {
    return;
  }

  const latitudeInput = document.querySelector("#geofenceLatitude");
  const longitudeInput = document.querySelector("#geofenceLongitude");
  const radiusInput = document.querySelector("#geofenceRadius");

  const savedLatitude = Number(latitudeInput.value);
  const savedLongitude = Number(longitudeInput.value);

  const hasSavedCoordinates =
    Number.isFinite(savedLatitude) &&
    Number.isFinite(savedLongitude) &&
    latitudeInput.value !== "" &&
    longitudeInput.value !== "";

  // Dar es Salaam is the fallback starting position.
  const startingLatitude = hasSavedCoordinates
    ? savedLatitude
    : -6.7924;

  const startingLongitude = hasSavedCoordinates
    ? savedLongitude
    : 39.2083;

  const startingPosition = [
    startingLatitude,
    startingLongitude,
  ];

  const radius = Number(radiusInput.value || 100);

  if (!geofenceMap) {
    geofenceMap = L.map("geofenceMap").setView(
      startingPosition,
      hasSavedCoordinates ? 17 : 12,
    );

    L.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      },
    ).addTo(geofenceMap);

    geofenceMarker = L.marker(startingPosition, {
      draggable: true,
    }).addTo(geofenceMap);

    geofenceCircle = L.circle(startingPosition, {
      radius,
    }).addTo(geofenceMap);

    geofenceMarker.bindPopup(
      "Church location. Drag this pin to adjust it.",
    );

    geofenceMap.on("click", (event) => {
      setGeofenceCoordinates(
        event.latlng.lat,
        event.latlng.lng,
        false,
      );
    });

    geofenceMarker.on("dragend", () => {
      const position = geofenceMarker.getLatLng();

      setGeofenceCoordinates(
        position.lat,
        position.lng,
        false,
      );
    });
  } else {
    geofenceMarker.setLatLng(startingPosition);
    geofenceCircle.setLatLng(startingPosition);
    geofenceCircle.setRadius(radius);

    if (hasSavedCoordinates) {
      geofenceMap.setView(startingPosition, 17);
    }
  }

  // The dashboard is hidden before login, so Leaflet must recalculate its size.
  window.setTimeout(() => {
    geofenceMap.invalidateSize();
  }, 100);
};

const renderGeofenceSettings = () => {
  const geofence = state.geofence || {};

  document.querySelector("#geofenceEnabled").checked =
    Boolean(geofence.geofence_enabled);

  document.querySelector("#geofenceLatitude").value =
    geofence.latitude ?? "";

  document.querySelector("#geofenceLongitude").value =
    geofence.longitude ?? "";

  const radius = Number(geofence.attendance_radius_meters || 100);

  document.querySelector("#geofenceRadius").value = radius;
  document.querySelector("#geofenceRadiusValue").textContent = radius;

  const configured =
    geofence.latitude !== null &&
    geofence.latitude !== undefined &&
    geofence.longitude !== null &&
    geofence.longitude !== undefined;

  document.querySelector("#geofenceSettingsStatus").innerHTML = configured
    ? `
        <strong>Church location configured.</strong>
        <span>
          ${geofence.latitude}, ${geofence.longitude} —
          ${radius} metre radius.
        </span>
      `
    : `
        <strong>Church location not configured.</strong>
        <span>Select a setup method and enter the church location.</span>
      `;
  updateGeofenceSetupMethod();
  initializeGeofenceMap();
};

const updateGeofenceSetupMethod = () => {
  const selectedMethod =
    document.querySelector(
      'input[name="setup_method"]:checked',
    )?.value || "map";

  const mapMode = document.querySelector("#geofenceMapMode");
  const manualMode = document.querySelector(
    "#geofenceManualMode",
  );

  const latitudeInput = document.querySelector(
    "#geofenceLatitude",
  );

  const longitudeInput = document.querySelector(
    "#geofenceLongitude",
  );

  mapMode.hidden = selectedMethod !== "map";
  manualMode.hidden = selectedMethod !== "manual";

  latitudeInput.readOnly = selectedMethod === "map";
  longitudeInput.readOnly = selectedMethod === "map";

  if (selectedMethod === "map" && geofenceMap) {
    window.setTimeout(() => {
      geofenceMap.invalidateSize();
    }, 100);
  }
};

const renderAdmin = () => {
  const roles = state.admin?.roles || [];
  const users = state.admin?.users || [];
  const auditLogs = state.admin?.audit_logs || [];
  const branch = state.admin?.branch || {};
  const roleSelect = document.querySelector("#adminUserRole");

  roleSelect.innerHTML = roles
    .filter((role) => role.slug !== "member")
    .map((role) => `<option value="${role.slug}">${role.name}</option>`)
    .join("");

  document.querySelector("#adminRoleList").innerHTML =
    roles
      .map((role) =>
        row({
          title: role.name,
          subtitle: role.description || "No description",
          tag: role.slug,
        }),
      )
      .join("") || emptyState("No roles configured.");

  document.querySelector("#adminUserList").innerHTML =
    users
      .map((user) =>
        row({
          title: user.name,
          subtitle: [user.email, user.phone || "No phone"].join(" - "),
          tag: `${labelize(user.primary_role)} / ${labelize(user.status)}`,
          tone: user.status === "active" ? "green" : "muted",
          action: `<button class="mini-button" data-admin-edit-user="${user.id}" type="button">Edit</button>`,
        }),
      )
      .join("") || emptyState("No staff users configured.");

  document.querySelector("#auditLogList").innerHTML =
    auditLogs
      .map((log) =>
        row({
          title: labelize(log.action),
          subtitle: `${log.actor} - ${labelize(log.entity_type)} - ${formatDateTime(log.created_at)}`,
          tag: log.metadata?.role ? labelize(log.metadata.role) : labelize(log.entity_type),
          tone: "amber",
        }),
      )
      .join("") || emptyState("No audit events yet.");

  document.querySelector("#branchName").value = branch.name || "";
  document.querySelector("#branchLocation").value = branch.location || "";
  document.querySelector("#branchPhone").value = branch.contact_phone || "";
  document.querySelector("#branchSettingsSummary").textContent = branch.id
    ? `${branch.name} - ${branch.location || "No location"} - ${
        branch.contact_phone || "No phone"
      }`
    : "No branch settings available.";
  document.querySelector("#backupManifestSummary").textContent = state.backupManifest
    ? `Last manifest: ${formatDateTime(state.backupManifest.generated_at)} - ${
        Object.keys(state.backupManifest.table_counts || {}).length
      } tables`
    : "No backup manifest exported this session.";

  document.querySelectorAll("[data-admin-edit-user]").forEach((button) => {
    button.addEventListener("click", () => openAdminUserForm(button.dataset.adminEditUser));
  });
  applyRoleAccess();
};

const deleteServiceTemplate = async (templateId) => {
  const template = (state.serviceTemplates || []).find(
    (item) => item.id === templateId,
  );

  if (!template) {
    return;
  }

  const confirmed = window.confirm(
    `Delete recurring service "${template.name}"?`,
  );

  if (!confirmed) {
    return;
  }

  try {
    setBusy(true);
    setStatus("Deleting recurring service");

    await sendJson(
      `/attendance/service-templates/${templateId}`,
      "DELETE",
    );

    await loadSection("attendance");

    setStatus("Recurring service deleted", "ok");
  } catch (error) {
    console.error(error);

    setStatus(
      error.message || "Recurring service could not be deleted",
      "error",
    );
  } finally {
    setBusy(false);
  }
};

const loadSection = async (section) => {
  if (section === "people") {
    state.people = await fetchJson("/members/");
    renderPeople();
  }
  if (section === "imports") {
    renderImportPreview();
  }
  if (section === "attendance") {
  const [attendance, serviceTemplates] = await Promise.all([
    fetchJson("/attendance/"),
    fetchJson("/attendance/service-templates"),
  ]);

  state.attendance = attendance;
  state.serviceTemplates = serviceTemplates;

  renderAttendance();
  }
  if (section === "households") {
    state.households = await fetchJson("/members/households");
    renderHouseholds();
  }
  if (section === "messages") {
    state.messages = await fetchJson("/messages/");
    renderMessages();
  }
  if (section === "stewardship") {
    state.stewardship = await fetchJson("/stewardship/");
    renderStewardship();
  }
  if (section === "reports") {
    state.reports = await fetchJson("/reports/weekly");
    renderWeeklyReport();
  }
  if (section === "settings") {
    const response = await fetchJson("/admin/branch/geofence");
    state.geofence = response.geofence || null;
    renderGeofenceSettings();
  }
  if (section === "admin") {
    const [roles, users, auditLogs, branch] = await Promise.all([
      fetchJson("/admin/roles"),
      fetchJson("/admin/users"),
      fetchJson("/admin/audit-logs"),
      fetchJson("/admin/branch"),
    ]);
    state.admin = {
      roles: roles.roles || [],
      users: users.users || [],
      audit_logs: auditLogs.audit_logs || [],
      branch: branch.branch || null,
    };
    renderAdmin();
  }
};

const loadDashboard = async () => {
  try {
    setBusy(true);
    setStatus("Connecting");
    setSkeletons();
    await Promise.all(permittedSections().map(loadSection));
    setStatus("API Connected", "ok");
  } catch (error) {
    console.error(error);
    if (String(error.message || "").includes("401")) {
      state.auth = null;
      localStorage.removeItem("parishconnect_auth");
      applyRoleAccess();
      setStatus("Login required", "error");
      return;
    }
    setStatus("API Offline", "error");
  } finally {
    setBusy(false);
  }
};

const login = async (form) => {
  try {
    setBusy(true);
    setStatus("Logging in");
    state.auth = await sendJson("/auth/login", "POST", formPayload(form));
    localStorage.setItem("parishconnect_auth", JSON.stringify(state.auth));
    applyRoleAccess();
    await loadDashboard();
    setStatus("Logged in", "ok");
  } catch (error) {
    console.error(error);
    state.auth = null;
    localStorage.removeItem("parishconnect_auth");
    applyRoleAccess();
    setStatus(error.message || "Login failed", "error");
  } finally {
    setBusy(false);
  }
};

const clearSession = () => {
  state.auth = null;
  state.people = null;
  state.attendance = null;
  state.households = null;
  state.messages = null;
  state.messageRecipients = null;
  state.stewardship = null;
  state.reports = null;
  state.admin = null;
  state.backupManifest = null;
  state.importPreview = null;
  localStorage.removeItem("parishconnect_auth");
  applyRoleAccess();
  setStatus("Logged out");
};

const logout = async () => {
  try {
    if (state.auth?.access_token) {
      await sendJson("/auth/logout", "POST");
    }
  } catch (error) {
    console.warn(error);
  } finally {
    clearSession();
  }
};

const copyText = async (text) => {
  if (navigator.clipboard) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.append(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
};

const copyWeeklyReportBriefing = async () => {
  try {
    setBusy(true);
    setStatus("Preparing briefing");
    const text = await fetchText("/reports/weekly/briefing");
    await copyText(text);
    setStatus("Briefing copied", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Copy failed", "error");
  } finally {
    setBusy(false);
  }
};

const downloadTextFile = (fileName, content, type = "text/csv") => {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

const downloadWeeklyReportCsv = async () => {
  try {
    setBusy(true);
    setStatus("Preparing CSV");
    const text = await fetchText("/reports/weekly.csv");
    downloadTextFile("parishconnect-weekly-report.csv", text);
    setStatus("CSV ready", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "CSV export failed", "error");
  } finally {
    setBusy(false);
  }
};

const downloadBackupManifest = async () => {
  try {
    setBusy(true);
    setStatus("Preparing backup manifest");
    state.backupManifest = await sendJson("/admin/backup-manifest", "POST");
    downloadTextFile(
      "parishconnect-backup-manifest.json",
      JSON.stringify(state.backupManifest, null, 2),
      "application/json",
    );
    renderAdmin();
    await loadSection("admin");
    setStatus("Backup manifest ready", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Backup manifest failed", "error");
  } finally {
    setBusy(false);
  }
};

const printWeeklyReport = async () => {
  if (!state.reports) {
    await loadSection("reports");
  }
  window.print();
};

const renderCheckInEventOptions = () => {
  const select = document.querySelector("#checkInEventSelect");
  const events = state.attendance?.events || [];
  select.innerHTML =
    events
      .map((event) => `<option value="${event.id}">${event.name}</option>`)
      .join("") || '<option value="">Create an event first</option>';
};

const renderCheckInPersonOptions = () => {
  const select = document.querySelector("#checkInPersonSelect");
  const personType = document.querySelector("#checkInPersonType").value;
  const people =
    personType === "member" ? state.people?.members || [] : state.people?.visitors || [];
  select.innerHTML =
    people
      .filter((person) => person.status !== "deceased" && person.follow_up_status !== "converted")
      .map((person) => `<option value="${person.id}">${person.name}</option>`)
      .join("") || `<option value="">No ${personType}s available</option>`;
};

const renderHouseholdMemberOptions = () => {
  const select = document.querySelector("#householdPrimaryMember");
  const members = state.people?.members || [];
  select.innerHTML =
    '<option value="">No primary adult</option>' +
    members
      .filter((member) => member.status === "active")
      .map((member) => `<option value="${member.id}">${member.name}</option>`)
      .join("");
};

const renderHouseholdOptions = () => {
  const select = document.querySelector("#dependentHouseholdSelect");
  const households = state.households?.households || [];
  select.innerHTML =
    households
      .map((household) => `<option value="${household.id}">${household.name}</option>`)
      .join("") || '<option value="">Create a household first</option>';
};

const renderContributionMemberOptions = () => {
  const select = document.querySelector("#contributionMemberSelect");
  if (!select) {
    return;
  }
  const members = state.people?.members || [];
  select.innerHTML =
    '<option value="">Anonymous / visitor</option>' +
    members
      .filter((member) => member.status === "active")
      .map((member) => `<option value="${member.id}">${member.name}</option>`)
      .join("");
};

const dateInputToIso = (value) => (value ? new Date(value).toISOString() : null);

const scanUrlFor = (eventId, token) =>
  `${window.location.origin}/scan.html?event_id=${encodeURIComponent(eventId)}&token=${encodeURIComponent(
    token,
  )}`;

const eventPayload = (form) => {
  const payload = formPayload(form);
  if (payload.starts_at) {
    payload.starts_at = dateInputToIso(payload.starts_at);
  }
  payload.qr_opens_at = dateInputToIso(payload.qr_opens_at);
  payload.qr_closes_at = dateInputToIso(payload.qr_closes_at);
  payload.qr_rotation_seconds = Number(payload.qr_rotation_seconds || 60);
  return payload;
};

const showQrToken = async (eventId) => {
  const panel = document.querySelector("#qrTokenPanel");
  try {
    setBusy(true);
    setStatus("Loading QR");
    const data = await fetchJson(`/attendance/events/${eventId}/qr-token`);
    const scanUrl = data.token ? scanUrlFor(eventId, data.token) : "";
    const qrImageUrl = data.token
      ? `${API_BASE}/attendance/events/${eventId}/qr-code.svg?data=${encodeURIComponent(scanUrl)}`
      : "";
    panel.innerHTML = `
      <div class="qr-display">
        <div class="qr-code-frame">
          ${
            qrImageUrl
              ? `<img src="${qrImageUrl}" alt="Attendance QR code for ${data.event.name}">`
              : `<span>QR opens at ${formatDateTime(data.opens_at)}</span>`
          }
        </div>
        <div>
          <strong>${data.event.name}</strong>
          <span>${data.active ? "QR attendance is open" : "QR attendance is closed"}</span>
          <code>${data.token || "Token unavailable until the attendance window opens."}</code>
          ${scanUrl ? `<a class="mini-button link-button" href="${scanUrl}" target="_blank" rel="noreferrer">Open scan page</a>` : ""}
        </div>
      </div>
      <div class="qr-meta">
        <span>Opens: ${formatDateTime(data.opens_at)}</span>
        <span>Closes: ${formatDateTime(data.closes_at)}</span>
        <span>Rotates: ${data.rotation_seconds}s</span>
        <span>Expires: ${formatDateTime(data.expires_at)}</span>
      </div>
    `;
    setStatus(data.active ? "QR Ready" : "QR Scheduled", data.active ? "ok" : "");
  } catch (error) {
    console.error(error);
    panel.innerHTML = `<span>${error.message || "QR token failed"}</span>`;
    setStatus(error.message || "QR failed", "error");
  } finally {
    setBusy(false);
  }
};

const openEventEditForm = (eventId) => {
  const event = state.attendance?.events?.find(
    (item) => item.id === eventId,
  );

  if (!event) {
    return;
  }

  const form = document.querySelector("#eventForm");

  form.elements.event_id.value = event.id;
  form.elements.name.value = event.name || "";
  form.elements.event_type.value = event.type || "service";
  form.elements.starts_at.value = event.starts_at
    isoToLocalInput(event.starts_at)
  form.elements.ends_at.value = event.ends_at
    isoToLocalInput(event.ends_at)
  form.elements.location.value = event.location || "";
  form.elements.qr_opens_at.value = event.qr_opens_at
    isoToLocalInput(event.qr_opens_at)
  form.elements.qr_closes_at.value = event.qr_closes_at
    isoToLocalInput(event.qr_closes_at)
  form.elements.qr_rotation_seconds.value =
    event.qr_rotation_seconds || 60;

  document.querySelector("#eventFormTitle").textContent =
    `Edit ${event.name}`;

  document.querySelector("#eventSubmitButton").textContent =
    "Save changes";

  document.querySelector("#cancelEventEdit").hidden = false;

  form.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
};


const clearEventForm = () => {
  const form = document.querySelector("#eventForm");

  form.reset();
  form.elements.event_id.value = "";
  form.elements.qr_rotation_seconds.value = 60;

  document.querySelector("#eventFormTitle").textContent =
    "Create Event";

  document.querySelector("#eventSubmitButton").textContent =
    "Create event";

  document.querySelector("#cancelEventEdit").hidden = true;
};
const isoToLocalInput = (value) => {
  if (!value) {
    return "";
  }

  const date = new Date(value);

  const pad = (number) => String(number).padStart(2, "0");

  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate(),
  )}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const deleteEvent = async (eventId) => {
  const event = state.attendance?.events?.find(
    (item) => item.id === eventId,
  );

  if (!event) {
    return;
  }

  const confirmed = window.confirm(
    `Delete "${event.name}"?`,
  );

  if (!confirmed) {
    return;
  }

  try {
    setBusy(true);
    setStatus("Deleting event");

    await sendJson(
      `/attendance/events/${eventId}`,
      "DELETE",
    );

    await loadSection("attendance");

    setStatus("Event deleted", "ok");
  } catch (error) {
    console.error(error);

    setStatus(
      error.message || "Event could not be deleted",
      "error",
    );
  } finally {
    setBusy(false);
  }
};

const clearServiceTemplateForm = () => {
  const form = document.querySelector("#serviceTemplateForm");

  form.reset();
  form.elements.template_id.value = "";
  form.elements.qr_open_minutes_before.value = 30;
  form.elements.qr_close_minutes_after.value = 30;
  form.elements.qr_rotation_seconds.value = 60;
  form.elements.is_active.checked = true;

  document.querySelector("#serviceTemplateFormTitle").textContent =
    "Add recurring service";

  document.querySelector("#serviceTemplateSubmitButton").textContent =
    "Save recurring service";

  document.querySelector("#cancelServiceTemplateEdit").hidden = true;
}; 


const submitServiceTemplateForm = async (form) => {
  const payload = formPayload(form);
  const templateId = payload.template_id;

  delete payload.template_id;

  payload.day_of_week = Number(payload.day_of_week);
  payload.qr_open_minutes_before = Number(
    payload.qr_open_minutes_before || 30,
  );
  payload.qr_close_minutes_after = Number(
    payload.qr_close_minutes_after || 30,
  );
  payload.qr_rotation_seconds = Number(
    payload.qr_rotation_seconds || 60,
  );

  payload.is_active = form.elements.is_active.checked;

  try {
    setBusy(true);

    if (templateId) {
      setStatus("Updating recurring service");

      await sendJson(
        `/attendance/service-templates/${templateId}`,
        "PATCH",
        payload,
      );

      setStatus("Recurring service updated", "ok");
    } else {
      setStatus("Creating recurring service");

      await sendJson(
        "/attendance/service-templates",
        "POST",
        payload,
      );

      setStatus("Recurring service created", "ok");
    }
    clearServiceTemplateForm();

    await loadSection("attendance");
  } catch (error) {
    console.error(error);

    setStatus(
      error.message || "Recurring service save failed",
      "error",
    );
  } finally {
    setBusy(false);
  }
};

const openServiceTemplateEditForm = (templateId) => {
  const template = (state.serviceTemplates || []).find(
    (item) => item.id === templateId,
  );

  if (!template) {
    setStatus("Recurring service not found", "error");
    return;
  }

  const form = document.querySelector("#serviceTemplateForm");

  form.elements.template_id.value = template.id;
  form.elements.name.value = template.name || "";
  form.elements.event_type.value = template.event_type || "service";
  form.elements.day_of_week.value = String(template.day_of_week);
  form.elements.start_time.value = template.start_time || "";
  form.elements.end_time.value = template.end_time || "";
  form.elements.location.value = template.location || "";
  form.elements.qr_open_minutes_before.value =
    template.qr_open_minutes_before ?? 30;
  form.elements.qr_close_minutes_after.value =
    template.qr_close_minutes_after ?? 30;
  form.elements.qr_rotation_seconds.value =
    template.qr_rotation_seconds ?? 60;
  form.elements.is_active.checked = Boolean(template.is_active);

  document.querySelector("#serviceTemplateFormTitle").textContent =
    `Edit ${template.name}`;

  document.querySelector("#serviceTemplateSubmitButton").textContent =
    "Save changes";

  document.querySelector("#cancelServiceTemplateEdit").hidden = false;

  form.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
};

const submitEventForm = async (form) => {
  const payload = eventPayload(form);
  const eventId = payload.event_id;

  delete payload.event_id;

  payload.qr_rotation_seconds = Number(
    payload.qr_rotation_seconds || 60,
  );

  try {
    setBusy(true);

    if (eventId) {
      setStatus("Updating event");

      await sendJson(
        `/attendance/events/${eventId}`,
        "PATCH",
        payload,
      );

      setStatus("Event updated", "ok");
    } else {
      setStatus("Creating event");

      await sendJson(
        "/attendance/events",
        "POST",
        payload,
      );

      setStatus("Event created", "ok");
    }

    clearEventForm();
    await loadSection("attendance");
  } catch (error) {
    console.error(error);

    setStatus(
      error.message || "Event save failed",
      "error",
    );
  } finally {
    setBusy(false);
  }
};

const submitCheckInForm = async (form) => {
  try {
    setBusy(true);
    setStatus("Checking in");
    await sendJson("/attendance/check-ins", "POST", formPayload(form));
    await loadSection("attendance");
    setStatus("Check-in recorded", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Check-in failed", "error");
  } finally {
    setBusy(false);
  }
};

const messagePayload = (form) => {
  const payload = formPayload(form);
  payload.scheduled_at = dateInputToIso(payload.scheduled_at);
  return payload;
};

const updateMessageAssist = () => {
  const body = document.querySelector("#messageBody").value || "";
  const channel = document.querySelector("#messageChannel").value;
  const counter = document.querySelector("#smsCounter");
  const preview = document.querySelector("#messagePreview");
  counter.textContent =
    channel === "sms"
      ? `${body.length} / 160 SMS characters`
      : `${body.length} characters`;
  counter.classList.toggle("warning", channel === "sms" && body.length > 160);
  preview.textContent = body || "Your message preview will appear here.";
};

const applyMessageTemplate = () => {
  const template = messageTemplates[document.querySelector("#messageTemplate").value];
  if (!template) {
    return;
  }
  const form = document.querySelector("#messageForm");
  form.elements.subject.value = template.subject;
  form.elements.body.value = template.body;
  updateMessageAssist();
};

const submitMessageForm = async (form) => {
  try {
    setBusy(true);
    setStatus("Saving message");
    await sendJson("/messages/", "POST", messagePayload(form));
    form.reset();
    updateMessageAssist();
    await loadSection("messages");
    setStatus("Message saved", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Message failed", "error");
  } finally {
    setBusy(false);
  }
};

const showMessageRecipients = async (messageId) => {
  const panel = document.querySelector("#messageRecipientList");
  try {
    setBusy(true);
    setStatus("Loading delivery");
    panel.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div>';
    state.messageRecipients = await fetchJson(`/messages/${messageId}/recipients`);
    renderMessages();
    document.querySelector("#messageRecipientList").scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
    setStatus("Delivery loaded", "ok");
  } catch (error) {
    console.error(error);
    panel.innerHTML = emptyState(error.message || "Delivery failed.");
    setStatus(error.message || "Delivery failed", "error");
  } finally {
    setBusy(false);
  }
};

const dispatchMessage = async (messageId) => {
  try {
    setBusy(true);
    setStatus("Dispatching message");
    const message = await sendJson(`/messages/${messageId}/dispatch`, "POST");
    await loadSection("messages");
    state.messageRecipients = await fetchJson(`/messages/${message.id}/recipients`);
    renderMessages();
    setStatus("Message dispatched", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Dispatch failed", "error");
  } finally {
    setBusy(false);
  }
};

const submitContributionForm = async (form) => {
  const payload = formPayload(form);
  payload.amount = Number(payload.amount || 0);

  try {
    setBusy(true);
    setStatus("Recording contribution");
    const contribution = await sendJson("/stewardship/contributions", "POST", payload);
    form.reset();
    document.querySelector("#contributionReceipt").innerHTML = `
      <strong>Recorded ${formatCurrency(contribution.amount, contribution.currency)}</strong>
      <span>${contribution.member_name || "Anonymous / Visitor"} - ${
        contribution.reference_code ? `Ref: ${contribution.reference_code}` : labelize(contribution.payment_method)
      }</span>
    `;
    await loadSection("stewardship");
    setStatus("Contribution recorded", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Contribution failed", "error");
  } finally {
    setBusy(false);
  }
};

const importPayload = () => ({
  import_type: document.querySelector("#importType").value,
  csv_text: document.querySelector("#importCsvText").value,
  file_name: document.querySelector("#importFile").files[0]?.name || "pasted.csv",
});

const previewImportCsv = async () => {
  try {
    setBusy(true);
    setStatus("Previewing import");
    state.importPreview = await sendJson("/imports/preview", "POST", importPayload());
    renderImportPreview();
    setStatus("Import preview ready", "ok");
  } catch (error) {
    console.error(error);
    state.importPreview = null;
    renderImportPreview();
    setStatus(error.message || "Import preview failed", "error");
  } finally {
    setBusy(false);
  }
};

const commitImportCsv = async () => {
  try {
    setBusy(true);
    setStatus("Importing rows");
    const result = await sendJson("/imports/commit", "POST", importPayload());
    state.importPreview = {
      ...result,
      total_rows: result.import.total_rows,
      valid_rows: result.import.successful_rows,
      failed_rows: result.import.failed_rows,
    };
    renderImportPreview();
    await loadSection("people");
    setStatus("Import complete", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Import failed", "error");
  } finally {
    setBusy(false);
  }
};

const downloadImportTemplate = () => {
  const importType = document.querySelector("#importType").value;
  const defaultStatus = importType === "members" ? "active" : "new";
  const sample =
    "first_name,last_name,phone,email,status\n" +
    `Sample,Person,+255 700 000 000,sample.person@example.test,${defaultStatus}\n`;
  downloadTextFile(`parishconnect-${importType}-template.csv`, sample);
};

const readImportFile = async (file) => {
  if (!file) {
    return;
  }
  document.querySelector("#importCsvText").value = await file.text();
  state.importPreview = null;
  renderImportPreview();
};

const clearAdminUserForm = () => {
  const form = document.querySelector("#adminUserForm");
  form.reset();
  form.elements.user_id.value = "";
  document.querySelector("#adminUserFormTitle").textContent = "Create Staff User";
  document.querySelector("#adminUserSubmit").textContent = "Create user";
  form.elements.password.required = true;
};

const openAdminUserForm = (userId) => {
  const user = (state.admin?.users || []).find((item) => item.id === userId);
  if (!user) {
    setStatus("User not found", "error");
    return;
  }
  const form = document.querySelector("#adminUserForm");
  form.elements.user_id.value = user.id;
  form.elements.name.value = user.name || "";
  form.elements.email.value = user.email || "";
  form.elements.phone.value = user.phone || "";
  form.elements.role.value = user.primary_role || "";
  form.elements.status.value = user.status || "active";
  form.elements.password.value = "";
  form.elements.password.required = false;
  document.querySelector("#adminUserFormTitle").textContent = `Edit ${user.name}`;
  document.querySelector("#adminUserSubmit").textContent = "Save user";
};

const submitAdminUserForm = async (form) => {
  const payload = formPayload(form);
  const userId = payload.user_id;
  delete payload.user_id;
  if (!payload.password) {
    delete payload.password;
  }

  try {
    setBusy(true);
    setStatus(userId ? "Updating user" : "Creating user");
    await sendJson(userId ? `/admin/users/${userId}` : "/admin/users", userId ? "PATCH" : "POST", payload);
    clearAdminUserForm();
    await loadSection("admin");
    setStatus(userId ? "User updated" : "User created", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "User save failed", "error");
  } finally {
    setBusy(false);
  }
};

const submitGeofenceSettingsForm = async (form) => {
  const payload = formPayload(form);

  payload.geofence_enabled =
    form.elements.geofence_enabled.checked;

  payload.setup_method =
    form.elements.setup_method.value;

  payload.latitude =
    payload.latitude === null
      ? null
      : Number(payload.latitude);

  payload.longitude =
    payload.longitude === null
      ? null
      : Number(payload.longitude);

  payload.attendance_radius_meters = Number(
    payload.attendance_radius_meters || 100,
  );

  const statusPanel = document.querySelector(
    "#geofenceSettingsStatus",
  );

  try {
    setBusy(true);
    setStatus("Saving geofence");

    const response = await sendJson(
      "/admin/branch/geofence",
      "PUT",
      payload,
    );

    state.geofence = response.geofence;

    renderGeofenceSettings();

    statusPanel.innerHTML = `
      <strong>Geofence settings saved.</strong>
      <span>
        ${response.geofence.latitude},
        ${response.geofence.longitude} —
        ${response.geofence.attendance_radius_meters}
        metre radius.
      </span>
    `;

    setStatus("Geofence saved", "ok");
  } catch (error) {
    console.error(error);

    statusPanel.innerHTML = `
      <strong>Geofence settings could not be saved.</strong>
      <span>${error.message || "Please check the values."}</span>
    `;

    setStatus(
      error.message || "Geofence save failed",
      "error",
    );
  } finally {
    setBusy(false);
  }
};

const submitBranchSettingsForm = async (form) => {
  try {
    setBusy(true);
    setStatus("Saving branch");
    await sendJson("/admin/branch", "PATCH", formPayload(form));
    await loadSection("admin");
    setStatus("Branch settings saved", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Branch save failed", "error");
  } finally {
    setBusy(false);
  }
};

const submitHouseholdForm = async (form) => {
  try {
    setBusy(true);
    setStatus("Creating household");
    await sendJson("/members/households", "POST", formPayload(form));
    form.reset();
    await loadSection("households");
    setStatus("Household created", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Household failed", "error");
  } finally {
    setBusy(false);
  }
};

const submitDependentForm = async (form) => {
  const payload = formPayload(form);
  const householdId = payload.household_id;
  delete payload.household_id;
  payload.can_self_check_in = false;

  try {
    setBusy(true);
    setStatus("Adding dependent");
    await sendJson(`/members/households/${householdId}/people`, "POST", payload);
    form.reset();
    form.elements.relationship.value = "child";
    await loadSection("households");
    setStatus("Dependent added", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Dependent failed", "error");
  } finally {
    setBusy(false);
  }
};

const submitPersonForm = async (form, path, successMessage) => {
  try {
    setBusy(true);
    setStatus("Saving");
    await sendJson(path, "POST", formPayload(form));
    form.reset();
    await loadSection("people");
    setStatus(successMessage, "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Save failed", "error");
  } finally {
    setBusy(false);
  }
};

const convertVisitor = async (visitorId) => {
  try {
    setBusy(true);
    setStatus("Converting");
    await sendJson(`/members/visitors/${visitorId}/convert`, "POST");
    await loadSection("people");
    setStatus("Visitor converted", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Convert failed", "error");
  } finally {
    setBusy(false);
  }
};

const updateMemberStatus = async (memberId, membershipStatus) => {
  const labels = {
    transferred: "mark this member as transferred to another church",
    deceased: "mark this member as deceased",
    discontinued: "mark this member as discontinued",
  };

  const confirmed = window.confirm(`Are you sure you want to ${labels[membershipStatus]}?`);
  if (!confirmed) {
    return;
  }

  try {
    setBusy(true);
    setStatus("Updating member");
    await sendJson(`/members/${memberId}`, "PATCH", { membership_status: membershipStatus });
    await loadSection("people");
    setStatus("Member updated", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Update failed", "error");
  } finally {
    setBusy(false);
  }
};

const statusOptions = {
  member: ["active", "transferred", "deceased", "discontinued"],
  visitor: ["new", "contacted", "converted"],
};

const openPersonDialog = (type, personId) => {
  const person =
    type === "member"
      ? state.people.members.find((member) => member.id === personId)
      : state.people.visitors.find((visitor) => visitor.id === personId);
  if (!person) {
    setStatus("Record not found", "error");
    return;
  }

  const dialog = document.querySelector("#personDialog");
  const form = document.querySelector("#personEditForm");
  const statusField = document.querySelector("#personStatusField");
  const statusValue = type === "member" ? person.status : person.follow_up_status;

  document.querySelector("#personDialogType").textContent = type === "member" ? "Member" : "Visitor";
  document.querySelector("#personDialogTitle").textContent = `Edit ${person.name}`;
  statusField.innerHTML = statusOptions[type]
    .map((option) => `<option value="${option}">${option}</option>`)
    .join("");

  form.elements.id.value = person.id;
  form.elements.type.value = type;
  form.elements.first_name.value = person.first_name || "";
  form.elements.last_name.value = person.last_name || "";
  form.elements.phone.value = person.phone || "";
  form.elements.email.value = person.email || "";
  form.elements.status.value = statusValue;

  dialog.showModal();
};

const submitEditForm = async (form) => {
  const payload = formPayload(form);
  const type = payload.type;
  const id = payload.id;
  const statusKey = type === "member" ? "membership_status" : "follow_up_status";
  const path = type === "member" ? `/members/${id}` : `/members/visitors/${id}`;

  delete payload.id;
  delete payload.type;
  payload[statusKey] = payload.status;
  delete payload.status;

  try {
    setBusy(true);
    setStatus("Saving changes");
    await sendJson(path, "PATCH", payload);
    document.querySelector("#personDialog").close();
    await loadSection("people");
    setStatus("Record updated", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Update failed", "error");
  } finally {
    setBusy(false);
  }
};

const updatePeopleFilters = () => {
  state.peopleFilters.query = document.querySelector("#peopleSearch").value.trim();
  state.peopleFilters.memberStatus = document.querySelector("#memberStatusFilter").value;
  state.peopleFilters.visitorStatus = document.querySelector("#visitorStatusFilter").value;
  renderPeople();
};

const setActiveNav = (sectionId) => {
  document.querySelectorAll("[data-section-link]").forEach((link) => {
    link.classList.toggle("active", link.dataset.sectionLink === sectionId);
  });
};

const setupStickyNavigation = () => {
  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (visible) {
        setActiveNav(visible.target.id);
      }
    },
    {
      rootMargin: "-15% 0px -65% 0px",
      threshold: [0.1, 0.25, 0.5, 0.75],
    },
  );

  navSections.forEach((sectionId) => {
    const section = document.getElementById(sectionId);
    if (section) {
      observer.observe(section);
    }
  });

  document.querySelectorAll("[data-section-link]").forEach((link) => {
    link.addEventListener("click", () => setActiveNav(link.dataset.sectionLink));
  });
};

document.querySelectorAll("[data-refresh]").forEach((button) => {
  button.addEventListener("click", async () => {
    try {
      if (!canUseSection(button.dataset.refresh)) {
        setStatus("No access", "error");
        return;
      }
      setBusy(true);
      setStatus("Refreshing");
      await loadSection(button.dataset.refresh);
      setStatus("API Connected", "ok");
    } catch (error) {
      console.error(error);
      setStatus("API Offline", "error");
    } finally {
      setBusy(false);
    }
  });
});
document
  .querySelector("#cancelEventEdit")
  ?.addEventListener("click", clearEventForm);
document.querySelector("#refreshAll").addEventListener("click", loadDashboard);
document.querySelector("#loginForm").addEventListener("submit", (event) => {
  event.preventDefault();
  login(event.currentTarget);
});
document.querySelector("#logoutButton").addEventListener("click", logout);
document.querySelector("#copyReportBriefing").addEventListener("click", copyWeeklyReportBriefing);
document.querySelector("#downloadReportCsv").addEventListener("click", downloadWeeklyReportCsv);
document.querySelector("#printReport").addEventListener("click", printWeeklyReport);
document.querySelector("#memberForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitPersonForm(event.currentTarget, "/members/", "Member added");
});
document.querySelector("#visitorForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitPersonForm(event.currentTarget, "/members/visitors", "Visitor added");
});
document.querySelector("#eventForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitEventForm(event.currentTarget);
});
document
  .querySelector("#serviceTemplateForm")
  ?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitServiceTemplateForm(event.currentTarget);
  });
document.querySelector("#checkInForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitCheckInForm(event.currentTarget);
});
document.querySelector("#messageForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitMessageForm(event.currentTarget);
});
document.querySelector("#messageTemplate").addEventListener("change", applyMessageTemplate);
document.querySelector("#messageBody").addEventListener("input", updateMessageAssist);
document.querySelector("#messageChannel").addEventListener("change", updateMessageAssist);
document.querySelector("#contributionForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitContributionForm(event.currentTarget);
});
document.querySelector("#previewImport").addEventListener("click", previewImportCsv);
document.querySelector("#commitImport").addEventListener("click", commitImportCsv);
document.querySelector("#downloadImportTemplate").addEventListener("click", downloadImportTemplate);
document.querySelector("#importFile").addEventListener("change", (event) => {
  readImportFile(event.currentTarget.files[0]);
});
document.querySelector("#adminUserForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitAdminUserForm(event.currentTarget);
});
document.querySelector("#branchSettingsForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitBranchSettingsForm(event.currentTarget);
});
document.querySelector("#downloadBackupManifest").addEventListener("click", downloadBackupManifest);
document.querySelector("#clearAdminUserForm").addEventListener("click", clearAdminUserForm);
document.querySelector("#householdForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitHouseholdForm(event.currentTarget);
});
document.querySelector("#dependentForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitDependentForm(event.currentTarget);
});
document.querySelector("#checkInPersonType").addEventListener("change", renderCheckInPersonOptions);
document.querySelector("#personEditForm").addEventListener("submit", (event) => {
  event.preventDefault();
  submitEditForm(event.currentTarget);
});
document.querySelector("#closePersonDialog").addEventListener("click", () => {
  document.querySelector("#personDialog").close();
});
document
  .querySelectorAll('input[name="setup_method"]')
  .forEach((radio) => {
    radio.addEventListener("change", updateGeofenceSetupMethod);
  });

document
  .querySelector("#geofenceRadius")
  .addEventListener("input", (event) => {
    const radius = Number(event.currentTarget.value);

    document.querySelector(
      "#geofenceRadiusValue",
    ).textContent = radius;

    if (geofenceCircle) {
      geofenceCircle.setRadius(radius);
    }
  });
  document
  .querySelector("#generateRecurringServices")
  ?.addEventListener("click", generateRecurringServices);
document
  .querySelector("#geofenceSettingsForm")
  .addEventListener("submit", (event) => {
    event.preventDefault();
    submitGeofenceSettingsForm(event.currentTarget);
  });
[
  "#geofenceLatitude",
  "#geofenceLongitude",
].forEach((selector) => {
  document
    .querySelector(selector)
    .addEventListener("change", () => {
      const latitude = document.querySelector(
        "#geofenceLatitude",
      ).value;

      const longitude = document.querySelector(
        "#geofenceLongitude",
      ).value;

      setGeofenceCoordinates(latitude, longitude);
    });
});
updateGeofenceSetupMethod();
document.querySelector("#peopleSearch").addEventListener("input", updatePeopleFilters);
document.querySelector("#memberStatusFilter").addEventListener("change", updatePeopleFilters);
document.querySelector("#visitorStatusFilter").addEventListener("change", updatePeopleFilters);
document
  .querySelector("#serviceDayToggleAttendance")
  ?.addEventListener("click", toggleServiceDayAttendance);

document
  .querySelector("#serviceDayShowQr")
  ?.addEventListener("click", () => {
    const eventId =
      document.querySelector("#serviceDayShowQr")?.dataset.eventId;

    if (eventId) {
      showQrToken(eventId);
    }
  });

setupStickyNavigation();
applyRoleAccess();
updateMessageAssist();

if (state.auth?.access_token) {
  loadDashboard();
} else {
  setStatus("Login required");
}
document
  .querySelector("#cancelServiceTemplateEdit")
  ?.addEventListener("click", clearServiceTemplateForm);