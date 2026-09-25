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

  const groupCard = (group, type) => {
    const details = [];
    if (group.area) details.push(group.area);
    if (group.meeting_day) details.push("Meets " + group.meeting_day);
    if (group.leader_name) details.push("Led by " + group.leader_name);

    const badge = group.is_leader ? "Leader" : labelize(group.role || "member");
    const detailLine = details.length ? details.join(" • ") : "Membership active";
    const kind = type === "community" ? labelize(group.group_type || "community") : "Ministry";

    return '<article class="member-group-card">' +
      '<div class="member-group-icon"><img src="./assets/icon-groups.svg" alt=""></div>' +
      '<div class="member-group-copy">' +
        '<div class="member-group-title"><strong>' + escapeHtml(group.name) + '</strong>' +
          '<span>' + escapeHtml(badge) + '</span></div>' +
        '<small>' + escapeHtml(kind) + '</small>' +
        '<p>' + escapeHtml(detailLine) + '</p>' +
        '<div class="member-group-meta"><span>' +
          escapeHtml(String(group.member_count || 0)) + ' members</span></div>' +
      '</div>' +
    '</article>';
  };

  const renderGroups = (data) => {
    const communities = data.communities || [];
    const ministries = data.ministries || [];
    const communityLabel = data.community_label || "Community Group";

    qs("#groupMembershipCount").textContent = String(data.total_memberships || 0);
    qs("#communityHeading").textContent = communityLabel + (communityLabel.endsWith("s") ? "" : "s");
    qs("#communityCount").textContent = String(communities.length);
    qs("#ministryCount").textContent = String(ministries.length);

    qs("#communityGroups").innerHTML = communities.length
      ? communities.map((group) => groupCard(group, "community")).join("")
      : '<div class="groups-empty">You are not linked to an active ' +
        escapeHtml(communityLabel.toLowerCase()) + ' yet.</div>';

    qs("#ministries").innerHTML = ministries.length
      ? ministries.map((group) => groupCard(group, "ministry")).join("")
      : '<div class="groups-empty">You are not linked to an active ministry yet.</div>';
  };

  const loadGroups = async () => {
    try {
      const data = await VinyrdClient.apiRequest("/member-portal/groups");
      renderGroups(data);
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
      showToast("Could not load your groups.");
    }
  };

  loadGroups();
}
