const API_BASE =
  window.VINYRD_API_BASE ||
  (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost"
    ? "http://127.0.0.1:8003/api/v1"
    : "/api/v1");

const STAFF_AUTH_KEY = "vinyrd_staff_auth";
const LEGACY_AUTH_KEY = "parishconnect_auth";
const storedStaffAuth =
  localStorage.getItem(STAFF_AUTH_KEY) || localStorage.getItem(LEGACY_AUTH_KEY);

if (!localStorage.getItem(STAFF_AUTH_KEY) && storedStaffAuth) {
  localStorage.setItem(STAFF_AUTH_KEY, storedStaffAuth);
  localStorage.removeItem(LEGACY_AUTH_KEY);
}

const state = {
  auth: JSON.parse(storedStaffAuth || "null"),
  people: null,
  communities: null,
  ministries: null,
  attendance: null,
  serviceTemplates: null,
  geofence: null,
  households: null,
  messages: null,
  messageRecipients: null,
  smsProvider: null,
  pastoral: null,
  sermons: null,
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
  "pastoral",
  "sermons",
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
  "pastoral",
  "sermons",
  "stewardship",
  "reports",
  "admin",
];



const labelize = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);

const formatCurrency = (amount, currency = "TZS") =>
  `${Number(amount || 0).toLocaleString()} ${currency}`;

const formatDateTime = (value) => (value ? new Date(value).toLocaleString() : "Not set");
const communityLabel = () =>
  state.admin?.branch?.community_label ||
  state.people?.configuration?.community_label ||
  "Community Group";

const communityLabelPlural = () => {
  const label = communityLabel();

  return label.endsWith("y")
    ? `${label.slice(0, -1)}ies`
    : `${label}s`;
};

const renderEventMinistryOptions = () => {
  const select =
    document.querySelector("#eventMinistrySelect");

  if (!select) {
    return;
  }

  const ministries =
    state.ministries?.ministries || [];

  select.innerHTML =
    '<option value="">Select ministry</option>' +
    ministries
      .map(
        (ministry) =>
          `<option value="${ministry.id}">${ministry.name}</option>`,
      )
      .join("");
};


const updateEventMinistryField = () => {
  const form = document.querySelector("#eventForm");

  if (!form) {
    return;
  }

  const typeSelect =
    form.elements.event_type;

  const ministryField =
    document.querySelector("#eventMinistryField");

  const ministrySelect =
    document.querySelector("#eventMinistrySelect");

  if (!typeSelect || !ministryField) {
    return;
  }

  const isMinistry =
    typeSelect.value === "ministry";

  ministryField.hidden = !isMinistry;

  if (!isMinistry && ministrySelect) {
    ministrySelect.value = "";
  }

  if (isMinistry) {
    renderEventMinistryOptions();
  }
};

const renderCommunityTerminology = () => {
  const label = communityLabel();

  const mappings = {
    addCommunityLabel: label.toLowerCase(),
    communityFormTitleLabel: label,
    communityNameLabel: label,
    createCommunityLabel: label.toLowerCase(),
    communityDialogTypeLabel: label,
    communityPanelTitle: communityLabelPlural(),
  };

  Object.entries(mappings).forEach(([id, value]) => {
    const element = document.querySelector(`#${id}`);

    if (element) {
      element.textContent = value;
    }
  });

  const description =
    document.querySelector("#communityPanelDescription");

  if (description) {
    description.textContent =
      `Manage ${communityLabelPlural().toLowerCase()} and their members.`;
  }
};

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
  pastor_leader: [
    "people",
    "attendance",
    "messages",
    "pastoral",
    "sermons",
    "stewardship",
    "reports",
    "settings",
  ],
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
    "#pastoralPrayerList",
    "#sermonEventList",
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





const dashboardNavigate = (sectionId) => {
  if (sectionId !== "overview" && !canUseSection(sectionId)) {
    setStatus("No access", "error");
    return;
  }

  const section = document.getElementById(sectionId);
  if (!section) {
    return;
  }

  window.location.hash = sectionId;
  setActiveNav(sectionId);
  section.scrollIntoView({ behavior: "smooth", block: "start" });
};

const renderDashboardOverview = () => {
  const accessCard = document.querySelector("#dashboardAccessCard");
  const pastoralCard = document.querySelector("#dashboardPastoralCard");
  const sermonCard = document.querySelector("#dashboardSermonCard");
  const servicesCard = document.querySelector("#dashboardServicesCard");

  if (!accessCard) {
    return;
  }

  accessCard.hidden = !canUseSection("people");
  pastoralCard.hidden = !canUseSection("pastoral");
  sermonCard.hidden = !canUseSection("sermons");
  servicesCard.hidden = !canUseSection("attendance");

  const accessList = document.querySelector("#dashboardMemberAccessList");
  if (accessList && canUseSection("people")) {
    const members = (state.people?.members || [])
      .filter((member) => member.status === "active")
      .slice(0, 4);

    accessList.innerHTML = members.length
      ? members
          .map(
            (member) => `
              <div class="snapshot-item">
                <div>
                  <strong>${escapeHtml(member.name)}</strong>
                  <small>${escapeHtml(member.email || member.phone || "No contact details")}</small>
                </div>
                <button class="mini-status" data-dashboard-member="${member.id}" type="button">Manage</button>
              </div>
            `,
          )
          .join("")
      : emptyState("No active members loaded.");

    document.querySelectorAll("[data-dashboard-member]").forEach((button) => {
      button.addEventListener("click", () => openMemberProfile(button.dataset.dashboardMember));
    });
  }

  const prayerList = document.querySelector("#dashboardPrayerList");
  if (prayerList && canUseSection("pastoral")) {
    const prayers = (state.pastoral?.prayers || []).slice(0, 4);
    prayerList.innerHTML = prayers.length
      ? prayers
          .map(
            (prayer) => `
              <div class="snapshot-item">
                <div>
                  <strong>${escapeHtml(prayer.member_name)}</strong>
                  <small>${escapeHtml(prayer.body)}</small>
                </div>
                <span class="mini-status ${prayer.status === "answered" ? "" : "gold"}">${escapeHtml(labelize(prayer.status))}</span>
              </div>
            `,
          )
          .join("")
      : emptyState("No prayer requests.");
  }

  const sermonList = document.querySelector("#dashboardSermonList");
  if (sermonList && canUseSection("sermons")) {
    const sermons = (state.sermons?.events || [])
      .filter((event) => event.title || event.summary || event.published)
      .slice(0, 4);

    sermonList.innerHTML = sermons.length
      ? sermons
          .map(
            (sermon) => `
              <div class="snapshot-item">
                <div>
                  <strong>${escapeHtml(sermon.title || sermon.event_name)}</strong>
                  <small>${escapeHtml(sermon.scripture_reference || sermon.event_name)}</small>
                </div>
                <span class="mini-status ${sermon.published ? "" : "gold"}">${sermon.published ? "Published" : "Draft"}</span>
              </div>
            `,
          )
          .join("")
      : emptyState("No sermon records yet.");
  }

  const serviceList = document.querySelector("#dashboardServiceList");
  if (serviceList && canUseSection("attendance")) {
    const now = Date.now();
    const allEvents = [...(state.attendance?.events || [])];
    const upcoming = allEvents
      .filter((event) => new Date(event.starts_at).getTime() >= now - 6 * 60 * 60 * 1000)
      .sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at))
      .slice(0, 4);
    const fallback = allEvents
      .sort((a, b) => new Date(b.starts_at) - new Date(a.starts_at))
      .slice(0, 4);
    const services = upcoming.length ? upcoming : fallback;

    serviceList.innerHTML = services.length
      ? services
          .map((event) => {
            const date = new Date(event.starts_at);
            return `
              <div class="service-preview-item">
                <div class="service-date">
                  <small>${date.toLocaleDateString(undefined, { month: "short" })}</small>
                  <b>${date.getDate()}</b>
                </div>
                <div>
                  <strong>${escapeHtml(event.name)}</strong>
                  <span>${escapeHtml(date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))}</span>
                  <small>${escapeHtml(event.location || "Location not set")}</small>
                </div>
              </div>
            `;
          })
          .join("")
      : emptyState("No services scheduled.");
  }
};

const applyRoleAccess = () => {
  const hasLogin = Boolean(state.auth?.access_token);
  const roles = currentRoles();
  document.querySelector("#loginScreen").hidden = hasLogin;
  document.querySelector("#appShell").hidden = !hasLogin;
  document.querySelector("#authSummary").textContent = hasLogin
    ? `${state.auth.user.name} - ${roles.map(labelize).join(", ")}`
    : "Guest mode";

  const userName = state.auth?.user?.name || "Vinyrd Staff";
  const firstName = userName.split(" ")[0] || "Friend";
  const primaryRole = roles[0] ? labelize(roles[0]) : "Staff Console";
  const welcomeName = document.querySelector("#welcomeUserName");
  const topbarName = document.querySelector("#topbarUserName");
  const topbarRole = document.querySelector("#topbarUserRole");
  const avatar = document.querySelector("#topbarAvatar");
  const currentDate = document.querySelector("#currentDate");

  if (welcomeName) welcomeName.textContent = firstName;
  if (topbarName) topbarName.textContent = userName;
  if (topbarRole) topbarRole.textContent = primaryRole;
  if (avatar) avatar.textContent = userName.slice(0, 1).toUpperCase();
  if (currentDate) {
    currentDate.textContent = new Intl.DateTimeFormat(undefined, {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(new Date());
  }
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

  if (hasLogin) {
    renderDashboardOverview();
  }

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

  const query = state.peopleFilters.query.trim();

  const showAll = query === "*";

  const members = allMembers.filter(
    (member) =>
      (showAll || (query && personMatchesQuery(member, query))) &&
      (state.peopleFilters.memberStatus === "all" ||
        member.status === state.peopleFilters.memberStatus),
  );

  const visitors = allVisitors.filter(
    (visitor) =>
      (showAll || (query && personMatchesQuery(visitor, query))) &&
      (state.peopleFilters.visitorStatus === "all" ||
        visitor.follow_up_status === state.peopleFilters.visitorStatus),
  );

  document.querySelector("#memberCount").textContent = allMembers.length;
  document.querySelector("#visitorCount").textContent = allVisitors.length;
  document.querySelector("#memberList").innerHTML =
  query
    ? members
        .map((member) =>
          row({
            title: member.name,
            subtitle: [
              member.phone || "No phone",
              member.email || "No email",
            ].join(" - "),
            tag: member.status,
            tone: member.status === "active" ? "green" : "muted",
            action: `
  <button
    class="mini-button"
    data-view-member="${member.id}"
    type="button"
  >
    View profile
  </button>

  <button
    class="mini-button"
    data-edit-member="${member.id}"
    type="button"
  >
    Edit
  </button>

  ${memberLifecycleActions(member)}
`,

          }),
          
        )
  
        .join("") || emptyState("No matching members found.")
    : emptyState("Search for a member to view records.");
  document.querySelectorAll("[data-view-member]").forEach((button) => {
  button.addEventListener("click", () => {
    openMemberProfile(button.dataset.viewMember);
  });
});
    document.querySelector("#visitorList").innerHTML =
  query
    ? visitors
        .map((visitor) =>
          row({
            title: visitor.name,
            subtitle: [
              visitor.phone || "No phone",
              visitor.email || "No email",
            ].join(" - "),
            tag: visitor.follow_up_status,
            tone: "amber",
            action: `
  <button
    class="mini-button"
    data-view-visitor="${visitor.id}"
    type="button"
  >
    View profile
  </button>

  <button
    class="mini-button"
    data-edit-visitor="${visitor.id}"
    type="button"
  >
    Edit
  </button>

  ${
    visitor.converted_member_id
      ? ""
      : `
        <button
          class="mini-button"
          data-convert-visitor="${visitor.id}"
          type="button"
        >
          Convert
        </button>
      `
  }
`,
          }),
        )
        .join("") || emptyState("No matching visitors found.")
    : emptyState("Search for a visitor to view records.");
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
  document
  .querySelectorAll("[data-view-visitor]")
  .forEach((button) => {
    button.addEventListener("click", () => {
      openVisitorProfile(
        button.dataset.viewVisitor,
      );
    });
  });
  renderCheckInPersonOptions();
  renderHouseholdMemberOptions();
  renderContributionMemberOptions();
  renderContributionHouseholdOptions();
  renderCommunityLeaderOptions();
  applyRoleAccess();
};
const renderCommunities = () => {
  const container = document.querySelector("#communityList");

  if (!container) {
    return;
  }

  const communities = state.communities?.communities || [];

  if (!communities.length) {
    container.innerHTML = `
      <div class="empty-state">
        <strong>No ${communityLabelPlural().toLowerCase()} yet</strong>
        <p>
          Create a ${communityLabel().toLowerCase()} to begin organising members
          into local pastoral groups.
        </p>
      </div>
    `;
    return;
  }

  container.innerHTML = communities
    .map(
      (community) => `
        <div class="community-card">
          <div class="community-card-main">
            <div>
              <div class="community-card-title">
                <strong>${community.name}</strong>

                <span class="tag ${
                  community.status === "active"
                    ? "green"
                    : ""
                }">
                  ${labelize(community.status)}
                </span>
              </div>

              <p class="muted">
                ${community.area || "Area not specified"}
                ${
                  community.meeting_day
                    ? ` · Meets ${community.meeting_day}`
                    : ""
                }
              </p>
            </div>

            <div class="community-card-stats">
              <strong>${community.member_count || 0}</strong>
              <span>Members</span>
            </div>
          </div>

          <div class="community-card-footer">
            <span>
              Leader:
              <strong>
                ${community.leader_name || "Not assigned"}
              </strong>
            </span>

            <button
              class="mini-button"
              data-view-community="${community.id}"
              type="button"
            >
              View ${communityLabel()}
            </button>
          </div>
        </div>
      `,
    )
    .join("");

  document
    .querySelectorAll("[data-view-community]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        openCommunityDialog(button.dataset.viewCommunity);
      });
    });
};
const renderMinistries = () => {
  const container = document.querySelector("#ministryList");

  if (!container) {
    return;
  }

  const ministries = state.ministries?.ministries || [];
  
  if (!ministries.length) {
    container.innerHTML = `
      <div class="empty-state">
        <strong>No ministries yet</strong>
        <p>
          Create a ministry to organise service teams and groups.
        </p>
      </div>
    `;
    return;
  }
  
  container.innerHTML = ministries
    .map(
      (ministry) => `
        <div class="community-card">
          <div class="community-card-main">
            <div>
              <div class="community-card-title">
                <strong>${ministry.name}</strong>
              </div>

              <p class="muted">
                Leader:
                ${ministry.leader_name || "Not assigned"}
              </p>
            </div>

            <div class="community-card-stats">
              <strong>${ministry.member_count || 0}</strong>
              <span>Members</span>
            </div>
          </div>

          <div class="community-card-footer">
            <button
              class="mini-button"
              data-view-ministry="${ministry.id}"
              type="button"
            >
              View ministry
            </button>
          </div>
        </div>
      `,
    )
    .join("");

  document
    .querySelectorAll("[data-view-ministry]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        openMinistryDialog(button.dataset.viewMinistry);
      });
    });
};
const showCommunityForm = () => {
  const communityForm =
    document.querySelector("#communityForm");

  const memberForm =
    document.querySelector("#memberForm");

  const visitorForm =
    document.querySelector("#visitorForm");

  if (!communityForm) {
    return;
  }

  communityForm.hidden = false;

  if (memberForm) {
    memberForm.hidden = true;
  }

  if (visitorForm) {
    visitorForm.hidden = true;
  }

  communityForm.scrollIntoView({
    behavior: "smooth",
    block: "center",
  });

  communityForm.querySelector("input")?.focus();
};
const hideCommunityForm = () => {
  const form =
    document.querySelector("#communityForm");

  if (form) {
    form.hidden = true;
  }
};
const submitCommunityForm = async (form) => {
  const payload = formPayload(form);

  try {
    setBusy(true);
    setStatus(`Creating ${communityLabel().toLowerCase()}`);

    await sendJson(
      "/members/communities",
      "POST",
      payload,
    );

    form.reset();
    form.hidden = true;

    await loadSection("people");

    setStatus(`${communityLabel()} created`, "ok");
  } catch (error) {
    console.error(error);

    setStatus(
      error.message || `${communityLabel()} creation failed`,
      "error",
    );
  } finally {
    setBusy(false);
  }
};
const renderMinistryLeaderOptions = () => {
  const select =
    document.querySelector("#ministryLeaderSelect");

  if (!select) {
    return;
  }

  const members = state.people?.members || [];

  select.innerHTML =
    '<option value="">No leader yet</option>' +
    members
      .filter((member) => member.status === "active")
      .map(
        (member) =>
          `<option value="${member.id}">${member.name}</option>`,
      )
      .join("");
};

const showMinistryForm = () => {
  const form = document.querySelector("#ministryForm");

  if (!form) {
    return;
  }

  form.hidden = false;
  renderMinistryLeaderOptions();

  form.scrollIntoView({
    behavior: "smooth",
    block: "center",
  });
};

const hideMinistryForm = () => {
  const form = document.querySelector("#ministryForm");

  if (form) {
    form.hidden = true;
  }
};

const submitMinistryForm = async (form) => {
  try {
    setBusy(true);
    setStatus("Creating ministry");

    await sendJson(
      "/members/ministries",
      "POST",
      formPayload(form),
    );

    form.reset();
    form.hidden = true;

    await loadSection("people");

    setStatus("Ministry created", "ok");
  } catch (error) {
    console.error(error);

    setStatus(
      error.message || "Ministry creation failed",
      "error",
    );
  } finally {
    setBusy(false);
  }
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
const ministryNameForEvent = (event) => {
  if (!event.ministry_id) {
    return null;
  }

  return (
    state.ministries?.ministries || []
  ).find(
    (ministry) =>
      ministry.id === event.ministry_id,
  )?.name || "Unknown ministry";
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
        subtitle: [
          formatDateTime(event.starts_at),
          event.ministry_id
            ? ministryNameForEvent(event)
            : null,
          event.location || "No location",
          `QR ${event.qr_active ? "open" : "closed"}`,
        ]
          .filter(Boolean)
          .join(" - "),
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
      }),
    )
    .join("") || emptyState("No upcoming events found.");  document.querySelector("#checkInList").innerHTML =
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



const renderPastoral = () => {
  const prayers = state.pastoral?.prayers || [];
  const list = document.querySelector("#pastoralPrayerList");
  if (!list) {
    return;
  }

  list.innerHTML =
    prayers
      .map((prayer) => {
        const contact = prayer.allow_contact
          ? [prayer.member_phone, prayer.member_email].filter(Boolean).join(" · ") ||
            "Contact allowed"
          : "Member requested no contact";
        const assignment = prayer.assigned_to
          ? `Assigned to ${escapeHtml(prayer.assigned_to)}`
          : "Unassigned";

        return `
          <article class="care-card">
            <div class="care-card-head">
              <div>
                <span class="eyebrow">${escapeHtml(labelize(prayer.category))}</span>
                <h3>${escapeHtml(prayer.member_name)}</h3>
                <p>${escapeHtml(contact)}</p>
              </div>
              <span class="tag ${prayer.status === "answered" ? "green" : "amber"}">
                ${escapeHtml(labelize(prayer.status))}
              </span>
            </div>
            <div class="care-prayer-text">${escapeHtml(prayer.body)}</div>
            <div class="care-meta">
              <span>${escapeHtml(labelize(prayer.visibility))}</span>
              <span>${assignment}</span>
              <span>Submitted ${escapeHtml(formatDateTime(prayer.created_at))}</span>
            </div>
            <div class="field-row">
              <label>
                Status
                <select data-prayer-status="${prayer.id}">
                  ${["submitted", "in_prayer", "contacted", "answered", "closed"]
                    .map(
                      (value) =>
                        `<option value="${value}" ${prayer.status === value ? "selected" : ""}>${labelize(value)}</option>`,
                    )
                    .join("")}
                </select>
              </label>
              <label>
                Assignment
                <select data-prayer-assignment="${prayer.id}">
                  <option value="keep">Keep current assignment</option>
                  <option value="me">Assign to me</option>
                  <option value="unassign">Unassign</option>
                </select>
              </label>
            </div>
            <label>
              Pastoral notes
              <textarea data-prayer-notes="${prayer.id}" rows="3" placeholder="Private pastoral follow-up notes">${escapeHtml(prayer.pastoral_notes || "")}</textarea>
            </label>
            <div class="dialog-actions">
              <button class="primary-button" data-save-prayer="${prayer.id}" type="button">
                Save prayer follow-up
              </button>
            </div>
          </article>
        `;
      })
      .join("") || emptyState("No prayer requests have been submitted yet.");

  document.querySelectorAll("[data-save-prayer]").forEach((button) => {
    button.addEventListener("click", async () => {
      const prayerId = button.dataset.savePrayer;
      const assignment = document.querySelector(
        `[data-prayer-assignment="${prayerId}"]`,
      )?.value;
      const payload = {
        status: document.querySelector(
          `[data-prayer-status="${prayerId}"]`,
        )?.value,
        pastoral_notes: document.querySelector(
          `[data-prayer-notes="${prayerId}"]`,
        )?.value || null,
      };

      if (assignment === "me") {
        payload.assign_to_me = true;
      } else if (assignment === "unassign") {
        payload.assign_to_me = false;
      }

      try {
        setBusy(true);
        setStatus("Saving pastoral follow-up");
        await sendJson(`/staff/prayers/${prayerId}`, "PATCH", payload);
        await loadSection("pastoral");
        setStatus("Prayer follow-up saved", "ok");
      } catch (error) {
        console.error(error);
        setStatus(error.message || "Prayer follow-up could not be saved", "error");
      } finally {
        setBusy(false);
      }
    });
  });

  applyRoleAccess();
};

const clearSermonForm = () => {
  const form = document.querySelector("#sermonForm");
  if (!form) {
    return;
  }
  form.reset();
  document.querySelector("#sermonFormTitle").textContent = "Publish Sermon";
  document.querySelector("#sermonSubmitButton").textContent = "Save sermon";
};

const openSermonEditor = (eventId) => {
  const sermon = state.sermons?.events?.find((item) => item.event_id === eventId);
  const form = document.querySelector("#sermonForm");
  if (!sermon || !form) {
    return;
  }

  form.elements.event_id.value = sermon.event_id;
  form.elements.title.value = sermon.title || "";
  form.elements.speaker.value = sermon.speaker || "";
  form.elements.scripture_reference.value = sermon.scripture_reference || "";
  form.elements.summary.value = sermon.summary || "";
  form.elements.published.checked = Boolean(sermon.published);
  document.querySelector("#sermonFormTitle").textContent =
    `Edit sermon · ${sermon.event_name}`;
  document.querySelector("#sermonSubmitButton").textContent = "Update sermon";
  form.scrollIntoView({ behavior: "smooth", block: "center" });
};

const renderSermons = () => {
  const events = state.sermons?.events || [];
  const select = document.querySelector("#sermonEventSelect");
  const list = document.querySelector("#sermonEventList");
  if (!select || !list) {
    return;
  }

  const currentValue = select.value;
  select.innerHTML =
    '<option value="">Select a service or event</option>' +
    events
      .map(
        (event) =>
          `<option value="${event.event_id}">${escapeHtml(event.event_name)} · ${escapeHtml(
            formatDateTime(event.starts_at),
          )}</option>`,
      )
      .join("");
  if (events.some((event) => event.event_id === currentValue)) {
    select.value = currentValue;
  }

  list.innerHTML =
    events
      .filter((event) => event.title || event.summary || event.published)
      .map(
        (event) => `
          <article class="sermon-admin-card">
            <div>
              <span class="eyebrow">${escapeHtml(event.event_name)}</span>
              <h3>${escapeHtml(event.title || "Draft sermon")}</h3>
              <p>${escapeHtml(
                [event.speaker, event.scripture_reference].filter(Boolean).join(" · ") ||
                  "Speaker/scripture not set",
              )}</p>
            </div>
            <div class="row-actions">
              <span class="tag ${event.published ? "green" : "muted"}">
                ${event.published ? "Published" : "Draft"}
              </span>
              <button class="mini-button" data-edit-sermon="${event.event_id}" type="button">
                Edit
              </button>
            </div>
          </article>
        `,
      )
      .join("") || emptyState("No sermon records yet. Select a service above to add one.");

  document.querySelectorAll("[data-edit-sermon]").forEach((button) => {
    button.addEventListener("click", () => openSermonEditor(button.dataset.editSermon));
  });

  applyRoleAccess();
};

const submitSermonForm = async (form) => {
  const payload = formPayload(form);
  const eventId = payload.event_id;
  if (!eventId) {
    setStatus("Select a service or event first", "error");
    return;
  }

  payload.published = form.elements.published.checked;
  delete payload.event_id;

  try {
    setBusy(true);
    setStatus(payload.published ? "Publishing sermon" : "Saving sermon draft");
    await sendJson(`/staff/sermons/${eventId}`, "PUT", payload);
    await loadSection("sermons");
    clearSermonForm();
    setStatus(payload.published ? "Sermon published" : "Sermon draft saved", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Sermon could not be saved", "error");
  } finally {
    setBusy(false);
  }
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
            contribution.household_name ||
              contribution.member_name ||
              "Unknown contributor",
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
  renderContributionHouseholdOptions();
  updateContributionScope();
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
  document.querySelector("#branchDenomination").value =
  branch.denomination || "";

document.querySelector("#branchCommunityLabel").value =
  branch.community_label || "Community Group";

document.querySelector("#branchDefaultLanguage").value =
  branch.default_language || "en";

document.querySelector("#branchTimezone").value =
  branch.timezone || "Africa/Dar_es_Salaam";
  document.querySelector("#branchSettingsSummary").textContent =
  branch.id
    ? [
        branch.name,
        branch.denomination || "Denomination not set",
        branch.location || "No location",
        branch.community_label || "Community Group",
        (
          branch.default_language || "en"
        ).toUpperCase(),
      ].join(" - ")
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
  const [people, communities, ministries] = await Promise.all([
  fetchJson("/members/"),
  fetchJson("/members/communities"),
  fetchJson("/members/ministries"),
]);

state.people = people;
state.communities = communities;
state.ministries = ministries;

renderCommunityTerminology();
renderPeople();
renderCommunities();
renderMinistries();

  state.people = people;
  state.communities = communities;

  renderPeople();
  renderCommunities();
  renderCommunityTerminology();
}
  if (section === "imports") {
    renderImportPreview();
  }
 if (section === "attendance") {
  const [attendance, serviceTemplates, ministries] = await Promise.all([
    fetchJson("/attendance/"),
    fetchJson("/attendance/service-templates"),
    fetchJson("/members/ministries"),
  ]);

  state.attendance = attendance;
  state.serviceTemplates = serviceTemplates;
  state.ministries = ministries;

  renderEventMinistryOptions();
  updateEventMinistryField();
  renderAttendance();
}
  if (section === "households") {
    state.households = await fetchJson("/members/households");
    renderHouseholds();
  }
  if (section === "messages") {
    const [messages, smsProvider, ministries] = await Promise.all([
      fetchJson("/messages/"),
      fetchJson("/messages/sms/provider"),
      state.ministries ? Promise.resolve(state.ministries) : fetchJson("/members/ministries"),
    ]);
    state.messages = messages;
    state.smsProvider = smsProvider;
    state.ministries = ministries;
    renderSmsProviderStatus();
    renderMessageAudienceOptions();
    updateMessageAudienceTarget();
    updateMessageAssist();
    renderMessages();
  }
  if (section === "pastoral") {
    state.pastoral = await fetchJson("/staff/prayers");
    renderPastoral();
  }
  if (section === "sermons") {
    state.sermons = await fetchJson("/staff/sermons");
    renderSermons();
  }
  if (section === "stewardship") {
  state.stewardship = await fetchJson("/stewardship/");

  if (!state.people) {
    state.people = await fetchJson("/members/");
  }

  if (!state.households) {
    state.households = await fetchJson("/members/households");
  }

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

  renderDashboardOverview();
};

const loadDashboard = async () => {
  try {
    setBusy(true);
    setStatus("Connecting");
    setSkeletons();
    await Promise.all(permittedSections().map(loadSection));
    renderDashboardOverview();
    setStatus("API Connected", "ok");
  } catch (error) {
    console.error(error);
    if (String(error.message || "").includes("401")) {
      state.auth = null;
      localStorage.removeItem(STAFF_AUTH_KEY);
  localStorage.removeItem(LEGACY_AUTH_KEY);
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
    localStorage.setItem(STAFF_AUTH_KEY, JSON.stringify(state.auth));
    applyRoleAccess();
    await loadDashboard();
    setStatus("Logged in", "ok");
  } catch (error) {
    console.error(error);
    state.auth = null;
    localStorage.removeItem(STAFF_AUTH_KEY);
  localStorage.removeItem(LEGACY_AUTH_KEY);
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
  state.smsProvider = null;
  state.stewardship = null;
  state.reports = null;
  state.admin = null;
  state.backupManifest = null;
  state.importPreview = null;
  localStorage.removeItem(STAFF_AUTH_KEY);
  localStorage.removeItem(LEGACY_AUTH_KEY);
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

const renderContributionHouseholdOptions = () => {
  const select = document.querySelector("#contributionHouseholdSelect");

  if (!select) {
    return;
  }

  const households = state.households?.households || [];

  select.innerHTML =
    '<option value="">Select household</option>' +
    households
      .map(
        (household) =>
          `<option value="${household.id}">${household.name}</option>`,
      )
      .join("");
};

const updateContributionScope = () => {
  const scope = document.querySelector("#contributionScope")?.value || "individual";
  const memberField = document.querySelector("#contributionMemberField");
  const householdField = document.querySelector("#contributionHouseholdField");
  const memberSelect = document.querySelector("#contributionMemberSelect");
  const householdSelect = document.querySelector("#contributionHouseholdSelect");

  if (!memberField || !householdField) {
    return;
  }

  const isHousehold = scope === "household";

  memberField.hidden = isHousehold;
  householdField.hidden = !isHousehold;

  if (isHousehold && memberSelect) {
    memberSelect.value = "";
  }

  if (!isHousehold && householdSelect) {
    householdSelect.value = "";
  }
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
  updateEventMinistryField();

if (form.elements.ministry_id) {
  form.elements.ministry_id.value =
    event.ministry_id || "";
} 
  form.elements.starts_at.value =
  isoToLocalInput(event.starts_at);

form.elements.ends_at.value =
  isoToLocalInput(event.ends_at);

form.elements.location.value =
  event.location || "";

form.elements.qr_opens_at.value =
  isoToLocalInput(event.qr_opens_at);

form.elements.qr_closes_at.value =
  isoToLocalInput(event.qr_closes_at);
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
  if (form.elements.ministry_id) {
  form.elements.ministry_id.value = "";
}

updateEventMinistryField();
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
  if (
  payload.event_type !== "ministry" ||
  !payload.ministry_id
) {
  payload.ministry_id = null;
}
if (
  payload.event_type === "ministry" &&
  !payload.ministry_id
) {
  setStatus("Select a ministry for this event", "error");
  return;
}
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

const smsSegmentInfo = (body) => {
  const text = String(body || "");
  const unicode = [...text].some((character) => character.charCodeAt(0) > 127);
  const singleLimit = unicode ? 70 : 160;
  const multipartLimit = unicode ? 67 : 153;
  const segments =
    text.length <= singleLimit ? 1 : Math.max(1, Math.ceil(text.length / multipartLimit));
  return {
    characters: text.length,
    unicode,
    segments,
    singleLimit,
    multipartLimit,
  };
};

const renderSmsProviderStatus = () => {
  const panel = document.querySelector("#smsProviderStatus");
  if (!panel) {
    return;
  }

  const provider = state.smsProvider;
  if (!provider) {
    panel.innerHTML = `
      <div class="sms-provider-icon">SMS</div>
      <div>
        <span class="eyebrow">SMS Gateway</span>
        <strong>Checking provider configuration…</strong>
        <p>VINYRD will keep real carrier sending off until the gateway is configured.</p>
      </div>
      <span class="tag amber">Checking</span>
    `;
    return;
  }

  const mode = labelize(provider.mode);
  const sender = provider.sender_id ? `Sender ID: ${provider.sender_id}` : "Sender ID not set";
  const callback = provider.delivery_report_configured
    ? "Delivery reports ready"
    : "Delivery reports not configured";
  const liveTone = provider.external_sending && provider.ready ? "green" : "amber";

  panel.innerHTML = `
    <div class="sms-provider-icon">SMS</div>
    <div>
      <span class="eyebrow">SMS Gateway · ${escapeHtml(provider.provider || "Provider")}</span>
      <strong>${escapeHtml(provider.summary || "SMS provider status unavailable.")}</strong>
      <p>${escapeHtml(sender)} · ${escapeHtml(callback)}</p>
    </div>
    <span class="tag ${liveTone}">${escapeHtml(mode)}</span>
  `;
  panel.classList.toggle("external-sms-ready", Boolean(provider.external_sending && provider.ready));
};

const renderMessageAudienceOptions = () => {
  const select = document.querySelector("#messageAudienceTarget");
  if (!select) {
    return;
  }

  const current = select.value;
  const ministries = state.ministries?.ministries || [];
  select.innerHTML =
    '<option value="">Select ministry</option>' +
    ministries
      .map(
        (ministry) =>
          `<option value="${ministry.id}">${escapeHtml(ministry.name)}</option>`,
      )
      .join("");

  if (ministries.some((ministry) => ministry.id === current)) {
    select.value = current;
  }
};

const updateMessageAudienceTarget = () => {
  const type = document.querySelector("#messageAudienceType")?.value;
  const field = document.querySelector("#messageAudienceTargetField");
  const select = document.querySelector("#messageAudienceTarget");
  if (!field || !select) {
    return;
  }

  const needsMinistry = type === "ministry";
  field.hidden = !needsMinistry;
  select.required = needsMinistry;
  if (!needsMinistry) {
    select.value = "";
  }
};

const updateMessageSubmitLabel = () => {
  const button = document.querySelector("#messageSubmitButton");
  const channel = document.querySelector("#messageChannel")?.value;
  const status = document.querySelector("#messageStatus")?.value;
  if (!button) {
    return;
  }

  if (status === "draft") {
    button.textContent = "Save draft";
  } else if (status === "scheduled") {
    button.textContent = "Save scheduled message";
  } else if (channel === "sms") {
    button.textContent = state.smsProvider?.external_sending ? "Send SMS" : "Simulate SMS";
  } else {
    button.textContent = "Send message";
  }
};

const updateMessageAssist = () => {
  const body = document.querySelector("#messageBody").value || "";
  const channel = document.querySelector("#messageChannel").value;
  const counter = document.querySelector("#smsCounter");
  const preview = document.querySelector("#messagePreview");
  const segment = smsSegmentInfo(body);

  counter.textContent =
    channel === "sms"
      ? `${segment.characters} chars · ${segment.segments} SMS segment${segment.segments === 1 ? "" : "s"} · ${segment.unicode ? "Unicode" : "GSM-style"}`
      : `${body.length} characters`;
  counter.classList.toggle("warning", channel === "sms" && segment.segments > 1);
  preview.textContent = body || "Your message preview will appear here.";
  updateMessageSubmitLabel();
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
  const payload = messagePayload(form);
  const isImmediateSms = payload.channel === "sms" && payload.status === "send_now";

  try {
    setBusy(true);
    setStatus(
      isImmediateSms
        ? state.smsProvider?.external_sending
          ? "Submitting SMS to provider"
          : "Running SMS simulation"
        : "Saving message",
    );
    await sendJson("/messages/", "POST", payload);
    form.reset();
    renderMessageAudienceOptions();
    updateMessageAudienceTarget();
    updateMessageAssist();
    await loadSection("messages");
    setStatus(
      isImmediateSms
        ? state.smsProvider?.external_sending
          ? "SMS submitted to provider"
          : "SMS recorded in simulation mode"
        : "Message saved",
      "ok",
    );
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

  if (payload.contributor_scope === "individual") {
    payload.household_id = null;
  }

  if (payload.contributor_scope === "household") {
    payload.member_id = null;
  }

  try {
    setBusy(true);
    setStatus("Recording contribution");

    const contribution = await sendJson(
      "/stewardship/contributions",
      "POST",
      payload,
    );

    const contributorName =
      contribution.household_name ||
      contribution.member_name ||
      "Unknown contributor";

    form.reset();
    updateContributionScope();

    document.querySelector("#contributionReceipt").innerHTML = `
      <strong>
        Recorded ${formatCurrency(
          contribution.amount,
          contribution.currency,
        )}
      </strong>

      <span>
        ${contributorName} - ${
          contribution.reference_code
            ? `Ref: ${contribution.reference_code}`
            : labelize(contribution.payment_method)
        }
      </span>

      <span>
        Contribution acknowledgement created
      </span>
    `;

    await loadSection("stewardship");

    setStatus("Contribution recorded", "ok");
  } catch (error) {
    console.error(error);
    setStatus(
      error.message || "Contribution failed",
      "error",
    );
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

    await sendJson(
      "/admin/branch",
      "PATCH",
      formPayload(form),
    );

    await loadSection("admin");

    renderCommunityTerminology();
    renderCommunities();

    setStatus("Branch settings saved", "ok");
  } catch (error) {
    console.error(error);

    setStatus(
      error.message || "Branch save failed",
      "error",
    );
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



const canManageMemberAccess = () => {
  const roles = currentRoles();
  return roles.includes("administrator") || roles.includes("receptionist");
};

const renderMemberAccessPanel = (member, access, temporaryPassword = null) => {
  const panel = document.querySelector("#memberAccessPanel");
  if (!panel) {
    return;
  }

  const manage = canManageMemberAccess();
  if (!access.exists) {
    panel.innerHTML = `
      <p class="muted">This member has not been activated for the Vinyrd member app.</p>
      <label>
        Login email
        <input id="memberAccessEmail" type="email" value="${escapeHtml(access.email || member.email || "")}" placeholder="member@example.com">
      </label>
      ${manage ? '<button class="primary-button" id="provisionMemberAccess" type="button">Create Vinyrd access</button>' : ""}
    `;

    document.querySelector("#provisionMemberAccess")?.addEventListener("click", async () => {
      const email = document.querySelector("#memberAccessEmail")?.value?.trim() || null;
      try {
        setBusy(true);
        setStatus("Creating Vinyrd member access");
        const result = await sendJson(
          `/staff/member-access/${member.id}`,
          "POST",
          { email },
        );
        renderMemberAccessPanel(member, result, result.temporary_password);
        setStatus("Vinyrd member access created", "ok");
      } catch (error) {
        console.error(error);
        setStatus(error.message || "Member access could not be created", "error");
      } finally {
        setBusy(false);
      }
    });
    return;
  }

  panel.innerHTML = `
    <div class="profile-grid">
      <div><span>Login email</span><strong>${escapeHtml(access.email)}</strong></div>
      <div><span>Access</span><strong>${access.status === "active" ? "Active" : "Disabled"}</strong></div>
      <div><span>Activated</span><strong>${escapeHtml(formatDateTime(access.created_at))}</strong></div>
      <div><span>Last account update</span><strong>${escapeHtml(formatDateTime(access.updated_at))}</strong></div>
    </div>
    ${temporaryPassword ? `
      <div class="temporary-password">
        <strong>Temporary password</strong>
        <code id="temporaryMemberPassword">${escapeHtml(temporaryPassword)}</code>
        <button class="mini-button" id="copyTemporaryMemberPassword" type="button">Copy</button>
        <p>Share this password privately with the member. It is only shown in this response.</p>
      </div>
    ` : ""}
    ${manage ? `
      <div class="dialog-actions">
        <button class="icon-button" id="resetMemberPassword" type="button">Reset password</button>
        <button class="${access.status === "active" ? "danger-button" : "primary-button"}" id="toggleMemberAccess" type="button">
          ${access.status === "active" ? "Disable access" : "Enable access"}
        </button>
      </div>
    ` : ""}
  `;

  document.querySelector("#copyTemporaryMemberPassword")?.addEventListener("click", async () => {
    const value = document.querySelector("#temporaryMemberPassword")?.textContent || "";
    await navigator.clipboard?.writeText(value);
    setStatus("Temporary password copied", "ok");
  });

  document.querySelector("#resetMemberPassword")?.addEventListener("click", async () => {
    try {
      setBusy(true);
      const result = await sendJson(
        `/staff/member-access/${member.id}/reset-password`,
        "POST",
      );
      renderMemberAccessPanel(member, result, result.temporary_password);
      setStatus("Temporary password reset", "ok");
    } catch (error) {
      console.error(error);
      setStatus(error.message || "Password reset failed", "error");
    } finally {
      setBusy(false);
    }
  });

  document.querySelector("#toggleMemberAccess")?.addEventListener("click", async () => {
    const nextStatus = access.status === "active" ? "inactive" : "active";
    try {
      setBusy(true);
      const result = await sendJson(
        `/staff/member-access/${member.id}`,
        "PATCH",
        { status: nextStatus },
      );
      renderMemberAccessPanel(member, result);
      setStatus(nextStatus === "active" ? "Member access enabled" : "Member access disabled", "ok");
    } catch (error) {
      console.error(error);
      setStatus(error.message || "Member access could not be updated", "error");
    } finally {
      setBusy(false);
    }
  });
};

const loadMemberAccess = async (member) => {
  const panel = document.querySelector("#memberAccessPanel");
  if (!panel) {
    return;
  }

  try {
    const access = await fetchJson(`/staff/member-access/${member.id}`);
    renderMemberAccessPanel(member, access);
  } catch (error) {
    console.error(error);
    panel.innerHTML = '<p class="muted">Member access information is unavailable for this account.</p>';
  }
};


const openMemberProfile = (memberId) => {
  const member = state.people?.members?.find(
    (item) => item.id === memberId,
  );

  if (!member) {
    setStatus("Member not found", "error");
    return;
  }

  const dialog = document.querySelector("#memberProfileDialog");
  const communities = member.communities || [];

  document.querySelector("#memberProfileName").textContent =
    member.name || "Member";

  document.querySelector("#memberProfileStatus").textContent =
    labelize(member.status || "active");

  document.querySelector("#memberProfileBody").innerHTML = `
    <div class="profile-section">
      <h3>Contact</h3>
      <div class="profile-grid">
        <div>
          <span>Phone</span>
          <strong>${member.phone || "Not provided"}</strong>
        </div>

        <div>
          <span>Email</span>
          <strong>${member.email || "Not provided"}</strong>
        </div>
      </div>
    </div>

    <div class="profile-section">
      <h3>Vinyrd Access</h3>
      <div id="memberAccessPanel" class="member-access-panel">
        <p class="muted">Loading member access...</p>
      </div>
    </div>

    <div class="profile-section">
      <h3>Personal</h3>
      <div class="profile-grid">
        <div>
          <span>Gender</span>
          <strong>${labelize(member.gender || "Not specified")}</strong>
        </div>

        <div>
          <span>Date of birth</span>
          <strong>${member.date_of_birth || "Not provided"}</strong>
        </div>

        <div>
          <span>Marital status</span>
          <strong>${labelize(member.marital_status || "Not specified")}</strong>
        </div>

        <div>
          <span>Occupation</span>
          <strong>${member.occupation || "Not provided"}</strong>
        </div>
      </div>
    </div>

    <div class="profile-section">
      <h3>Location</h3>
      <div class="profile-grid">
        <div>
          <span>Area</span>
          <strong>${member.area || "Not provided"}</strong>
        </div>

        <div>
          <span>Address</span>
          <strong>${member.address || "Not provided"}</strong>
        </div>
      </div>
    </div>

    <div class="profile-section">
      <h3>${communityLabel()}</h3>

      ${
        communities.length
          ? communities
              .map(
                (community) => `
                  <div class="profile-community">
                    <strong>${community.name}</strong>
                    <span>
                      ${labelize(community.role || "member")}
                      ${
                        community.area
                          ? ` · ${community.area}`
                          : ""
                      }
                    </span>
                  </div>
                `,
              )
              .join("")
          : `<p>No ${communityLabel().toLowerCase()}assigned.</p>`
      }
    </div>
    <div class="profile-section">
  <h3>Ministries</h3>

  ${
    member.ministries?.length
      ? `
        <div class="profile-grid">
          ${member.ministries
            .map(
              (ministry) => `
                <div>
                  <span>${ministry.name}</span>

                  <strong>
                    ${
                      ministry.is_leader
                        ? "Leader"
                        : labelize(ministry.role || "member")
                    }
                  </strong>
                </div>
              `,
            )
            .join("")}
        </div>
      `
      : `
        <p class="muted">
          No ministry memberships.
        </p>
      `
  }
</div>
    <div class="profile-section">
  <h3>Household</h3>

  ${
    member.household
      ? `
        <div class="profile-grid">
       
          <div>
            <span>Household</span>
            <strong>
              ${member.household.name || "Not provided"}
            </strong>
          </div>

          <div>
            <span>Relationship</span>
            <strong>
              ${labelize(
                member.household.relationship || "Not specified"
              )}
            </strong>
          </div>

          <div>
            <span>Household role</span>
            <strong>
              ${
                member.household.is_primary_member
                  ? "Primary member"
                  : "Household member"
              }
            </strong>
          </div>

          <div>
            <span>Primary phone</span>
            <strong>
              ${member.household.primary_phone || "Not provided"}
            </strong>
          </div>
        </div>
         <div class="dialog-actions">
          <button
            class="mini-button"
            type="button"
            data-view-household="${member.household.id}"
          >
          View household
        </button>
        </div>
      `
      : `
        <p class="muted">
          This member is not linked to a household.
        </p>
      `
  }
</div>
    <div class="profile-section">
  <h3>${communityLabel()}assignment</h3>

  <div class="field-row">
    <label>
      ${communityLabel()}
      <select id="memberCommunitySelect">
        <option value="">Select ${communityLabel().toLowerCase()}</option>
      </select>
    </label>

    <label>
      Role
      <select id="memberCommunityRole">
        <option value="member">Member</option>
        <option value="leader">Leader</option>
        <option value="assistant">Assistant</option>
      </select>
    </label>
  </div>

  <div class="dialog-actions">
    <button
      class="primary-button"
      type="button"
      id="assignMemberCommunity"
    >
      Assign community
    </button>
  </div>
</div>

    <div class="profile-section">
      <h3>Preferences</h3>
      <div class="profile-grid">
        <div>
          <span>Preferred language</span>
          <strong>${labelize(member.preferred_language || "Not specified")}</strong>
        </div>
      </div>
    </div>

    <div class="profile-section">
      <h3>Notes</h3>
      <p>${member.notes || "No notes recorded."}</p>
    </div>
  `;

  const communitySelect =
  document.querySelector("#memberCommunitySelect");

if (communitySelect) {
  const groups = state.communities?.communities || [];

  communitySelect.innerHTML =
    '<option value="">Select community</option>' +
    groups
      .filter((group) => group.status === "active")
      .map(
        (group) =>
          `<option value="${group.id}">${group.name}</option>`,
      )
      .join("");
}




document
  .querySelector("#assignMemberCommunity")
  ?.addEventListener("click", async () => {
    const communityId =
      document.querySelector("#memberCommunitySelect")?.value;

    const role =
      document.querySelector("#memberCommunityRole")?.value || "member";

    if (!communityId) {
      setStatus(
  `Select a ${communityLabel().toLowerCase()} first`,
  "error",
);
      return;
    }

    try {
      setBusy(true);
      setStatus(`Assigning ${communityLabel().toLowerCase()}`);

      await sendJson(
        `/members/communities/${communityId}/members`,
        "POST",
        {
          member_id: member.id,
          role,
        },
      );

      await loadSection("people");

      document
        .querySelector("#memberProfileDialog")
        ?.close();

      setStatus(`${communityLabel()} assigned`, "ok");
    } catch (error) {
      console.error(error);

      setStatus(
        error.message || `${communityLabel()} assignment failed`,
        "error",
      );
    } finally {
      setBusy(false);
    }
  });

  document
  .querySelector("[data-view-household]")
  ?.addEventListener("click", async (event) => {
    const householdId =
      event.currentTarget.dataset.viewHousehold;

    if (!state.households) {
      state.households =
        await fetchJson("/members/households");
    }

    openHouseholdDialog(householdId);
  });

  dialog.showModal();
  loadMemberAccess(member);
};

const openVisitorProfile = (visitorId) => {
  const visitor =
    state.people?.visitors?.find(
      (item) => item.id === visitorId,
    );

  if (!visitor) {
    setStatus("Visitor not found", "error");
    return;
  }

  const dialog =
    document.querySelector("#visitorProfileDialog");

  document.querySelector(
    "#visitorProfileName",
  ).textContent = visitor.name || "Visitor";

  document.querySelector(
    "#visitorProfileStatus",
  ).textContent =
    labelize(visitor.follow_up_status || "new");

  document.querySelector(
    "#visitorProfileBody",
  ).innerHTML = `
    <div class="profile-section">
      <h3>Contact</h3>

      <div class="profile-grid">
        <div>
          <span>Phone</span>
          <strong>
            ${visitor.phone || "Not provided"}
          </strong>
        </div>

        <div>
          <span>Email</span>
          <strong>
            ${visitor.email || "Not provided"}
          </strong>
        </div>
      </div>
    </div>

    <div class="profile-section">
      <h3>Personal</h3>

      <div class="profile-grid">
        <div>
          <span>Gender</span>
          <strong>
            ${labelize(
              visitor.gender || "Not specified",
            )}
          </strong>
        </div>

        <div>
          <span>Preferred language</span>
          <strong>
            ${labelize(
              visitor.preferred_language ||
                "Not specified",
            )}
          </strong>
        </div>
      </div>
    </div>

    <div class="profile-section">
      <h3>Location</h3>

      <div class="profile-grid">
        <div>
          <span>Area</span>
          <strong>
            ${visitor.area || "Not provided"}
          </strong>
        </div>

        <div>
          <span>Address</span>
          <strong>
            ${visitor.address || "Not provided"}
          </strong>
        </div>
      </div>
    </div>

    <div class="profile-section">
      <h3>Follow-up</h3>

      <div class="profile-grid">
        <div>
          <span>Status</span>
          <strong>
            ${labelize(
              visitor.follow_up_status || "new",
            )}
          </strong>
        </div>

        <div>
          <span>Conversion</span>
          <strong>
            ${
              visitor.converted_member_id
                ? "Converted to member"
                : "Not converted"
            }
          </strong>
        </div>
      </div>
    </div>

    <div class="profile-section">
  <h3>Follow-up actions</h3>

  <div class="dialog-actions">
    ${
      visitor.follow_up_status === "new"
        ? `
          <button
            class="mini-button"
            type="button"
            id="markVisitorContacted"
          >
            Mark as contacted
          </button>
        `
        : ""
    }

    ${
      !visitor.converted_member_id
        ? `
          <button
            class="primary-button"
            type="button"
            id="convertVisitorFromProfile"
          >
            Convert to member
          </button>
        `
        : ""
    }
  </div>
</div>

    <div class="profile-section">
      <h3>Notes</h3>

      <p>
        ${visitor.notes || "No notes recorded."}
      </p>
    </div>
  `;

  
  document
  .querySelector("#markVisitorContacted")
  ?.addEventListener("click", async () => {
    try {
      setBusy(true);
      setStatus("Updating visitor");

      await sendJson(
        `/members/visitors/${visitor.id}`,
        "PATCH",
        {
          follow_up_status: "contacted",
        },
      );

      await loadSection("people");

      document
        .querySelector("#visitorProfileDialog")
        ?.close();

      setStatus("Visitor marked as contacted", "ok");
    } catch (error) {
      console.error(error);

      setStatus(
        error.message || "Visitor update failed",
        "error",
      );
    } finally {
      setBusy(false);
    }
  });
  document
  .querySelector("#convertVisitorFromProfile")
  ?.addEventListener("click", async () => {
    document
      .querySelector("#visitorProfileDialog")
      ?.close();

    await convertVisitor(visitor.id);
  });

  dialog.showModal();
};

const openHouseholdDialog = (householdId) => {
  const household =
    state.households?.households?.find(
      (item) => item.id === householdId,
    );

  if (!household) {
    setStatus("Household not found", "error");
    return;
  }

  const dialog =
    document.querySelector("#householdDialog");

  const body =
    document.querySelector("#householdDialogBody");

  document.querySelector(
    "#householdDialogName",
  ).textContent = household.name;

  body.innerHTML = `
    <div class="profile-section">
      <h3>Household information</h3>

      <div class="profile-grid">
        <div>
          <span>Primary contact</span>
          <strong>
            ${household.primary_contact || "Not assigned"}
          </strong>
        </div>

        <div>
          <span>Primary phone</span>
          <strong>
            ${household.primary_phone || "Not provided"}
          </strong>
        </div>

        <div>
          <span>People</span>
          <strong>
            ${household.people?.length || 0}
          </strong>
        </div>
      </div>
    </div>

    <div class="profile-section">
      <h3>Household members</h3>

      ${
        household.people?.length
          ? household.people
              .map(
                (person) => `
                 <div class="community-member-row">
    <div>
    <strong>${person.name}</strong>
    <span>
      ${labelize(person.relationship || "member")}
    </span>
    </div>

    <div class="row-actions">
    <span class="tag ${
      person.status === "active" ? "green" : "muted"
    }">
      ${labelize(person.status || "active")}
    </span>

    ${
      person.member_id
        ? `
          <button
            class="mini-button"
            type="button"
            data-household-view-member="${person.member_id}"
          >
            View profile
                          </button>
                         `
                      : ""
                    }
                  </div>
                </div>
                `,
              )
              .join("")
          : `
              <p class="muted">
                No household members found.
              </p>
            `
      }
    </div>

    ${
      household.notes
        ? `
          <div class="profile-section">
            <h3>Notes</h3>
            <p>${household.notes}</p>
          </div>
        `
        : ""
    }
  `;

  document
  .querySelectorAll("[data-household-view-member]")
  .forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelector("#householdDialog")?.close();

      openMemberProfile(
        button.dataset.householdViewMember,
      );
    });
  });


  dialog.showModal();
};

const openCommunityDialog = (communityId) => {
  const community =
    state.communities?.communities?.find(
      (item) => item.id === communityId,
    );

  if (!community) {
    setStatus("Community not found", "error");
    return;
  }

  const dialog = document.querySelector("#communityDialog");
  const body = document.querySelector("#communityDialogBody");

  document.querySelector("#communityDialogName").textContent =
    community.name;

  const members = community.members || [];

  body.innerHTML = `
    <div class="profile-section">
      <h3>${communityLabel()} information</h3>

      <div class="profile-grid">
        <div>
          <span>Area</span>
          <strong>${community.area || "Not provided"}</strong>
        </div>

        <div>
          <span>Meeting day</span>
          <strong>
            ${community.meeting_day || "Not specified"}
          </strong>
        </div>

        <div>
          <span>Leader</span>
          <strong>
            ${community.leader_name || "Not assigned"}
          </strong>
        </div>

        <div>
          <span>Members</span>
          <strong>${community.member_count || 0}</strong>
        </div>
      </div>
    </div>
    <div class="profile-section">
  <div class="panel-header">
    <div>
      <h3>Edit ${communityLabel().toLowerCase()}</h3>
      <p class="muted">
        Update the ${communityLabel().toLowerCase()} details or leader.
      </p>
    </div>

    <button
      class="mini-button"
      type="button"
      id="toggleCommunityEdit"
    >
      Edit
    </button>
  </div>

  <form
    id="communityEditForm"
    class="person-form"
    hidden
  >
    <div class="field-row">
      <label>
        Name
        <input
          name="name"
          value="${community.name || ""}"
          required
        >
      </label>

      <label>
        Area
        <input
          name="area"
          value="${community.area || ""}"
        >
      </label>
    </div>

    <div class="field-row">
      <label>
        Meeting day
        <select
          name="meeting_day"
          id="communityEditMeetingDay"
        >
          <option value="">Not specified</option>
          <option value="Monday">Monday</option>
          <option value="Tuesday">Tuesday</option>
          <option value="Wednesday">Wednesday</option>
          <option value="Thursday">Thursday</option>
          <option value="Friday">Friday</option>
          <option value="Saturday">Saturday</option>
          <option value="Sunday">Sunday</option>
        </select>
      </label>

      <label>
        Leader
        <select
          name="leader_member_id"
          id="communityEditLeader"
        >
          <option value="">No leader</option>
        </select>
      </label>
    </div>

    <label>
      Status
      <select name="status">
        <option value="active">Active</option>
        <option value="inactive">Inactive</option>
      </select>
    </label>

    <label>
      Notes
      <textarea
        name="notes"
        rows="3"
      >${community.notes || ""}</textarea>
    </label>

    <button
      class="primary-button"
      type="submit"
    >
      Save changes
    </button>
  </form>
</div>
    <div class="profile-section">
      <h3>Members</h3>

      ${
        members.length
          ? members
              .map(
                (membership) => `
               <div class="community-member-row">
  <div>
    <strong>${membership.member_name}</strong>
    <span>
      ${labelize(membership.role || "member")}
    </span>
  </div>

  <div class="row-actions">
    <span class="tag green">
      ${labelize(membership.status || "active")}
    </span>

    <button
      class="mini-button danger"
      type="button"
      data-remove-community-member="${membership.member_id}"
      data-community-id="${community.id}"
    >
      Remove
    </button>
  </div>
</div>
                `,
              )
              .join("")
          : `
              <p class="muted">
                No members have been assigned yet.
              </p>
            `
      }
    </div>

    ${
      community.notes
        ? `
          <div class="profile-section">
            <h3>Notes</h3>
            <p>${community.notes}</p>
          </div>
        `
        : ""
    }
  `;
  
  const editForm =
  document.querySelector("#communityEditForm");

const editToggle =
  document.querySelector("#toggleCommunityEdit");

const leaderSelect =
  document.querySelector("#communityEditLeader");

const meetingDaySelect =
  document.querySelector("#communityEditMeetingDay");

if (leaderSelect) {
  leaderSelect.innerHTML =
    '<option value="">No leader</option>' +
    (state.people?.members || [])
      .filter((member) => member.status === "active")
      .map(
        (member) =>
          `<option value="${member.id}">${member.name}</option>`,
      )
      .join("");

  leaderSelect.value =
    community.leader_member_id || "";
}

if (meetingDaySelect) {
  meetingDaySelect.value =
    community.meeting_day || "";
}

if (editForm) {
  editForm.elements.status.value =
    community.status || "active";
}

editToggle?.addEventListener("click", () => {
  editForm.hidden = !editForm.hidden;

  editToggle.textContent =
    editForm.hidden ? "Edit" : "Hide";
});
editForm?.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = formPayload(event.currentTarget);

  try {
    setBusy(true);
    setStatus(`Updating ${communityLabel().toLowerCase()}`);

    await sendJson(
      `/members/communities/${community.id}`,
      "PATCH",
      payload,
    );

    await loadSection("people");

    document
      .querySelector("#communityDialog")
      ?.close();

    setStatus(`${communityLabel()} updated`, "ok");
  } catch (error) {
    console.error(error);

    setStatus(
      error.message || `${communityLabel()} update failed`,
      "error",
    );
  } finally {
    setBusy(false);
  }
});
  document
  .querySelectorAll("[data-remove-community-member]")
  .forEach((button) => {
    button.addEventListener("click", async () => {
      const memberId =
        button.dataset.removeCommunityMember;

      const communityId =
        button.dataset.communityId;

      const membership =
        community.members.find(
          (item) => item.member_id === memberId,
        );

      const confirmed = window.confirm(
        `Remove ${
          membership?.member_name || "this member"
        } from ${community.name}?`,
      );

      if (!confirmed) {
        return;
      }

      try {
        setBusy(true);
        setStatus("Removing member");

        await sendJson(
          `/members/communities/${communityId}/members/${memberId}`,
          "DELETE",
        );

        await loadSection("people");

        document
          .querySelector("#communityDialog")
          ?.close();

        setStatus(
          `Member removed from ${communityLabel().toLowerCase()}`,
          "ok",
        );
      } catch (error) {
        console.error(error);

        setStatus(
          error.message ||
          `Could not remove ${communityLabel().toLowerCase()} member`,
          "error",
        );
      } finally {
        setBusy(false);
      }
    });
  });

  dialog.showModal();
};

const renderCommunityLeaderOptions = () => {
  const select =
    document.querySelector("#communityLeaderSelect");

  if (!select) {
    return;
  }

  const members = state.people?.members || [];

  select.innerHTML =
    '<option value="">No leader yet</option>' +
    members
      .filter((member) => member.status === "active")
      .map(
        (member) =>
          `<option value="${member.id}">${member.name}</option>`,
      )
      .join("");
};
const openMinistryDialog =  async (ministryId) => {
  const ministry = (state.ministries?.ministries || []).find(
    (item) => item.id === ministryId,
  );
  if (!state.attendance) {
  try {
    state.attendance = await fetchJson("/attendance/");
  } catch (error) {
    console.warn(
      "Could not load ministry attendance history",
      error,
    );
  }
}
  if (!ministry) {
    setStatus("Ministry not found", "error");
    return;
  }

  const dialog = document.querySelector("#ministryDialog");
  const body = document.querySelector("#ministryDialogBody");

  if (!dialog || !body) {
    return;
  }

  document.querySelector("#ministryDialogName").textContent =
    ministry.name;

  const members = ministry.members || [];
 
  const ministryEvents = (state.attendance?.events || [])
  .filter(
    (event) => event.ministry_id === ministry.id,
  )
  .sort(
    (a, b) =>
      new Date(a.starts_at).getTime() -
      new Date(b.starts_at).getTime(),
  );

const now = new Date();

const upcomingEvents = ministryEvents.filter(
  (event) => new Date(event.starts_at) >= now,
);

const pastEvents = ministryEvents
  .filter(
    (event) => new Date(event.starts_at) < now,
  )
  .reverse();

  body.innerHTML = `
    <div class="profile-section">
      <h3>Ministry information</h3>

      <div class="profile-grid">
        <div>
          <span>Leader</span>
          <strong>
            ${ministry.leader_name || "Not assigned"}
          </strong>
        </div>

        <div>
          <span>Members</span>
          <strong>${ministry.member_count || 0}</strong>
        </div>
      </div>
    </div>
    <div class="profile-section">
  <h3>Edit ministry</h3>

  <div class="field-row">
    <label>
      Ministry name
      <input
        id="ministryEditName"
        value="${ministry.name || ""}"
      >
    </label>

    <label>
      Leader
      <select id="ministryEditLeader">
        <option value="">No leader assigned</option>
      </select>
    </label>
  </div>

  <button
    class="primary-button"
    id="saveMinistryChanges"
    type="button"
  >
    Save ministry changes
  </button>
</div>
    <div class="profile-section">
      <h3>Add member</h3>

      <div class="field-row">
        <label>
          Member
          <select id="ministryMemberSelect">
            <option value="">Select member</option>
          </select>
        </label>

        <label>
          Role
          <input
            id="ministryMemberRole"
            value="member"
            placeholder="e.g. singer, usher"
          >
        </label>
      </div>

      <button
        class="primary-button"
        id="addMinistryMember"
        type="button"
      >
        Add member
      </button>
    </div>

    <div class="profile-section">
  <h3>Upcoming ministry events</h3>

  ${
    upcomingEvents.length
      ? upcomingEvents
          .map(
            (event) => `
              <div class="community-member-row">
                <div>
                  <strong>${event.name}</strong>
                  <span>
                    ${formatDateTime(event.starts_at)}
                    ${
                      event.location
                        ? ` · ${event.location}`
                        : ""
                    }
                  </span>
                </div>

                <div class="row-actions">
                  <span class="tag ${
                    event.attendance_status === "open"
                      ? "green"
                      : "muted"
                  }">
                    ${labelize(
                      event.attendance_status || "scheduled",
                    )}
                  </span>

                  <span class="tag">
                    ${event.check_ins || 0} check-ins
                  </span>
                </div>
              </div>
            `,
          )
          .join("")
      : `
          <p class="muted">
            No upcoming ministry events.
          </p>
        `
  }
</div>

<div class="profile-section">
  <h3>Past ministry activity</h3>

  ${
    pastEvents.length
      ? pastEvents
          .slice(0, 10)
          .map(
            (event) => `
              <div class="community-member-row">
                <div>
                  <strong>${event.name}</strong>
                  <span>
                    ${formatDateTime(event.starts_at)}
                    ${
                      event.location
                        ? ` · ${event.location}`
                        : ""
                    }
                  </span>
                </div>

                <div class="row-actions">
                  <span class="tag">
                    ${event.check_ins || 0} attended
                  </span>
                </div>
              </div>
            `,
          )
          .join("")
      : `
          <p class="muted">
            No past ministry activity yet.
          </p>
        `
  }
</div>

    <div class="profile-section">
      <h3>Ministry members</h3>

      <div class="community-member-list">
        ${
          members.length
            ? members
                .map(
                  (membership) => `
                    <div class="community-member-row">
                      <div>
                        <strong>
                          ${membership.member_name || "Unknown member"}
                        </strong>

                        <p class="muted">
                          ${labelize(membership.role || "member")}
                        </p>
                      </div>

                      <button
                        class="mini-button"
                        data-remove-ministry-member="${membership.member_id}"
                        data-ministry-id="${ministry.id}"
                        type="button"
                      >
                        Remove
                      </button>
                    </div>
                  `,
                )
                .join("")
            : `<p class="muted">No members assigned yet.</p>`
        }
      </div>
    </div>
  `;
  const leaderSelect =
  document.querySelector("#ministryEditLeader");

if (leaderSelect) {
  leaderSelect.innerHTML =
    '<option value="">No leader assigned</option>' +
    (state.people?.members || [])
      .filter((member) => member.status === "active")
      .map(
        (member) => `
          <option
            value="${member.id}"
            ${
              member.id === ministry.leader_member_id
                ? "selected"
                : ""
            }
          >
            ${member.name}
          </option>
        `,
      )
      .join("");
}
document
  .querySelector("#saveMinistryChanges")
  ?.addEventListener("click", async () => {
    const name =
      document.querySelector("#ministryEditName")?.value.trim();

    const leaderMemberId =
      document.querySelector("#ministryEditLeader")?.value || null;

    if (!name) {
      setStatus("Ministry name is required", "error");
      return;
    }

    try {
      setBusy(true);
      setStatus("Updating ministry");

      await sendJson(
        `/members/ministries/${ministry.id}`,
        "PATCH",
        {
          name,
          leader_member_id: leaderMemberId,
        },
      );

      await loadSection("people");

      const refreshed = (
        state.ministries?.ministries || []
      ).find((item) => item.id === ministry.id);

      if (refreshed) {
        openMinistryDialog(refreshed.id);
      }

      setStatus("Ministry updated", "ok");
    } catch (error) {
      console.error(error);

      setStatus(
        error.message || "Ministry update failed",
        "error",
      );
    } finally {
      setBusy(false);
    }
  });
  const memberSelect =
    document.querySelector("#ministryMemberSelect");

  const existingMemberIds = new Set(
    members.map((membership) => membership.member_id),
  );

  if (memberSelect) {
    memberSelect.innerHTML =
      '<option value="">Select member</option>' +
      (state.people?.members || [])
        .filter(
          (member) =>
            member.status === "active" &&
            !existingMemberIds.has(member.id),
        )
        .map(
          (member) =>
            `<option value="${member.id}">${member.name}</option>`,
        )
        .join("");
  }

  document
    .querySelector("#addMinistryMember")
    ?.addEventListener("click", async () => {
      const memberId =
        document.querySelector("#ministryMemberSelect")?.value;

      const role =
        document.querySelector("#ministryMemberRole")?.value.trim() ||
        "member";

      if (!memberId) {
        setStatus("Select a member first", "error");
        return;
      }

      try {
        setBusy(true);
        setStatus("Adding ministry member");

        await sendJson(
          `/members/ministries/${ministry.id}/members`,
          "POST",
          {
            member_id: memberId,
            role,
          },
        );

        await loadSection("people");

        const refreshed = (
          state.ministries?.ministries || []
        ).find((item) => item.id === ministry.id);

        if (refreshed) {
          openMinistryDialog(refreshed.id);
        }

        setStatus("Ministry member added", "ok");
      } catch (error) {
        console.error(error);

        setStatus(
          error.message || "Could not add ministry member",
          "error",
        );
      } finally {
        setBusy(false);
      }
    });

  document
    .querySelectorAll("[data-remove-ministry-member]")
    .forEach((button) => {
      button.addEventListener("click", async () => {
        const memberId =
          button.dataset.removeMinistryMember;

        const ministryId =
          button.dataset.ministryId;

        const membership = members.find(
          (item) => item.member_id === memberId,
        );

        const confirmed = window.confirm(
          `Remove ${
            membership?.member_name || "this member"
          } from ${ministry.name}?`,
        );

        if (!confirmed) {
          return;
        }

        try {
          setBusy(true);
          setStatus("Removing ministry member");

          await sendJson(
            `/members/ministries/${ministryId}/members/${memberId}`,
            "DELETE",
          );

          await loadSection("people");

          const refreshed = (
            state.ministries?.ministries || []
          ).find((item) => item.id === ministryId);

          if (refreshed) {
            openMinistryDialog(refreshed.id);
          }

          setStatus("Ministry member removed", "ok");
        } catch (error) {
          console.error(error);

          setStatus(
            error.message || "Could not remove ministry member",
            "error",
          );
        } finally {
          setBusy(false);
        }
      });
    });

  dialog.showModal();
};
const showPeopleForm = (type) => {
  const memberForm = document.querySelector("#memberForm");
  const visitorForm = document.querySelector("#visitorForm");

  if (!memberForm || !visitorForm) {
    return;
  }

  if (type === "member") {
    memberForm.hidden = false;
    visitorForm.hidden = true;

    memberForm.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });

    memberForm.querySelector("input")?.focus();
  }

  if (type === "visitor") {
    visitorForm.hidden = false;
    memberForm.hidden = true;

    visitorForm.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });

    visitorForm.querySelector("input")?.focus();
  }
};

const hidePeopleForm = (type) => {
  const form =
    type === "member"
      ? document.querySelector("#memberForm")
      : document.querySelector("#visitorForm");

  if (!form) {
    return;
  }

  form.hidden = true;
};
const downloadPeopleCsv = async () => {
  try {
    setBusy(true);
    setStatus("Preparing people CSV");

    const text = await fetchText("/members/export.csv");

    downloadTextFile(
      "vinard-people.csv",
      text,
      "text/csv",
    );

    setStatus("People CSV ready", "ok");
  } catch (error) {
    console.error(error);

    setStatus(
      error.message || "People CSV export failed",
      "error",
    );
  } finally {
    setBusy(false);
  }
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

document.querySelector("#globalSearchForm")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = document.querySelector("#globalSearch")?.value?.trim();
  if (!query) {
    return;
  }

  if (!canUseSection("people")) {
    setStatus("Your role does not have access to People search", "error");
    return;
  }

  try {
    setBusy(true);
    if (!state.people) {
      await loadSection("people");
    }
    state.peopleFilters.query = query;
    document.querySelector("#peopleSearch").value = query;
    renderPeople();
    dashboardNavigate("people");
    setStatus("People search ready", "ok");
  } catch (error) {
    console.error(error);
    setStatus(error.message || "Search failed", "error");
  } finally {
    setBusy(false);
  }
});

document.querySelectorAll("[data-dashboard-target]").forEach((button) => {
  button.addEventListener("click", () => dashboardNavigate(button.dataset.dashboardTarget));
});
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
document.querySelector("#sermonForm")?.addEventListener("submit", (event) => {
  event.preventDefault();
  submitSermonForm(event.currentTarget);
});
document.querySelector("#clearSermonForm")?.addEventListener("click", clearSermonForm);
document.querySelector("#messageTemplate").addEventListener("change", applyMessageTemplate);
document.querySelector("#messageBody").addEventListener("input", updateMessageAssist);
document.querySelector("#messageChannel").addEventListener("change", updateMessageAssist);
document.querySelector("#messageStatus").addEventListener("change", updateMessageAssist);
document.querySelector("#messageAudienceType").addEventListener("change", updateMessageAudienceTarget);
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
document
  .querySelector("#contributionScope")
  ?.addEventListener("change", updateContributionScope);
document
  .querySelector("#showMemberForm")
  ?.addEventListener("click", () => {
    showPeopleForm("member");
  });

document
  .querySelector("#showVisitorForm")
  ?.addEventListener("click", () => {
    showPeopleForm("visitor");
  });

document
  .querySelector("#downloadPeopleCsv")
  ?.addEventListener("click", downloadPeopleCsv);
document
  .querySelector("#showAllPeople")
  ?.addEventListener("click", () => {
    document.querySelector("#peopleSearch").value = "*";
    updatePeopleFilters();
  });
document
  .querySelector("#clearPeopleSearch")
  ?.addEventListener("click", () => {
    document.querySelector("#peopleSearch").value = "";
    updatePeopleFilters();
  });
document
  .querySelector("#hideMemberForm")
  ?.addEventListener("click", () => {
    hidePeopleForm("member");
  });

document
  .querySelector("#hideVisitorForm")
  ?.addEventListener("click", () => {
    hidePeopleForm("visitor");
  });
document
  .querySelector("#closeMemberProfile")
  ?.addEventListener("click", () => {
    document.querySelector("#memberProfileDialog")?.close();
  });
document
  .querySelector("#showCommunityForm")
  ?.addEventListener("click", showCommunityForm);

document
  .querySelector("#hideCommunityForm")
  ?.addEventListener("click", hideCommunityForm);

document
  .querySelector("#communityForm")
  ?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitCommunityForm(event.currentTarget);
  });

document
  .querySelector("#closeCommunityDialog")
  ?.addEventListener("click", () => {
    document.querySelector("#communityDialog")?.close();
  });

document
  .querySelector("#refreshCommunities")
  ?.addEventListener("click", async () => {
    state.communities =
      await fetchJson("/members/communities");

    renderCommunities();
    setStatus("Communities refreshed", "ok");
  });
document
  .querySelector("#closeHouseholdDialog")
  ?.addEventListener("click", () => {
    document
      .querySelector("#householdDialog")
      ?.close();
  });

document
  .querySelector("#closeVisitorProfile")
  ?.addEventListener("click", () => {
    document
      .querySelector("#visitorProfileDialog")
      ?.close();
  });
document
  .querySelector("#showMinistryForm")
  ?.addEventListener("click", showMinistryForm);

document
  .querySelector("#hideMinistryForm")
  ?.addEventListener("click", hideMinistryForm);

document
  .querySelector("#ministryForm")
  ?.addEventListener("submit", (event) => {
    event.preventDefault();
    submitMinistryForm(event.currentTarget);
  });

document
  .querySelector("#refreshMinistries")
  ?.addEventListener("click", async () => {
    state.ministries =
      await fetchJson("/members/ministries");

    renderMinistries();
    setStatus("Ministries refreshed", "ok");
  });

document
  .querySelector("#closeMinistryDialog")
  ?.addEventListener("click", () => {
    document.querySelector("#ministryDialog")?.close();
  });
document
  .querySelector("#eventForm")
  ?.elements.event_type
  ?.addEventListener(
    "change",
    updateEventMinistryField,
  );