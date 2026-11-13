(() => {
  const $ = (id) => document.getElementById(id);
  const node = (tag, text) => {
    const n = document.createElement(tag);
    if (text != null) n.textContent = text;
    return n;
  };
  const status = (text) => ($("networkAdminStatus").textContent = text);
  // Browser-only membership bubbles: no system permission, PII, or external provider.
  const toast = node("div");
  toast.id = "membershipToast";
  toast.className = "membership-toast";
  toast.hidden = true;
  document.body.append(toast);
  let toastTimeout = null;
  let countdownInterval = null;
  const dismissToast = () => {
    if (toastTimeout !== null) window.clearTimeout(toastTimeout);
    if (countdownInterval !== null) window.clearInterval(countdownInterval);
    toastTimeout = null;
    countdownInterval = null;
    toast.hidden = true;
  };
  const notify = (message, kind = "success") => {
    dismissToast();
    const duration = kind === "error" ? 12000 : 9000;
    const title = kind === "error" ? "Action needs attention"
      : kind === "info" ? "Membership requests" : "Vinyrd";
    toast.className = "membership-toast membership-toast--" + kind;
    toast.setAttribute("role", kind === "error" ? "alert" : "status");
    toast.setAttribute("aria-label", "Vinyrd membership notification");

    const icon = node("span", kind === "error" ? "!" : kind === "info" ? "✉" : "✓");
    icon.className = "membership-toast__icon";
    icon.setAttribute("aria-hidden", "true");
    const copy = node("div");
    copy.className = "membership-toast__copy";
    copy.append(node("strong", title), node("span", message));

    const timer = node("span");
    timer.className = "membership-toast__timer";
    timer.setAttribute("aria-hidden", "true");
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 44 44");
    svg.setAttribute("aria-hidden", "true");
    for (const cls of ["membership-toast__ring-track", "membership-toast__ring-progress"]) {
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", "22");
      circle.setAttribute("cy", "22");
      circle.setAttribute("r", "16");
      circle.setAttribute("class", cls);
      svg.append(circle);
    }
    svg.querySelector(".membership-toast__ring-progress").style.animationDuration = duration + "ms";
    const seconds = node("span", Math.ceil(duration / 1000) + "s");
    seconds.className = "membership-toast__seconds";
    timer.append(svg, seconds);

    const dismiss = node("button", "×");
    dismiss.type = "button";
    dismiss.className = "membership-toast__dismiss";
    dismiss.setAttribute("aria-label", "Dismiss notification");
    dismiss.addEventListener("click", dismissToast);
    toast.replaceChildren(icon, copy, timer, dismiss);
    toast.hidden = false;
    const deadline = Date.now() + duration;
    countdownInterval = window.setInterval(() => {
      seconds.textContent = Math.max(0, Math.ceil((deadline - Date.now()) / 1000)) + "s";
    }, 500);
    toastTimeout = window.setTimeout(dismissToast, duration);
  };
  const action = (label, callback) => {
    const b = node("button", label);
    b.type = "button";
    b.addEventListener("click", async () => {
      b.disabled = true;
      try {
        await callback();
      } catch (e) {
        status(e.message);
        notify("Action failed. Please check the message on this page.", "error");
      } finally {
        b.disabled = false;
      }
    });
    return b;
  };
  let offset = 0;
  let profilePublished = null;
  let knownPendingIds = null;
  let pollingStarted = false;
  let pollInFlight = false;

  // Membership requests are initiated by members in the public church directory,
  // not by the administrator's local People form.
  const guide = node("aside");
  guide.id = "membershipOnboardingGuide";
  guide.className = "membership-onboarding";
  guide.setAttribute("aria-label", "How church membership requests work");
  $("networkRequestStatus").closest("label").before(guide);

  const memberLink = (label, path) => {
    const link = node("a", label);
    link.href = path;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  };
  const renderGuide = () => {
    guide.replaceChildren();
    guide.append(node("h3", "How membership requests work"));
    const published = node(
      "p",
      profilePublished === null
        ? "Checking public church profile status…"
        : profilePublished
          ? "Church profile published — people can discover this church."
          : "Church profile not published — it will not appear in member discovery yet.",
    );
    published.className = profilePublished
      ? "membership-published"
      : "membership-unpublished";
    guide.append(published);

    const steps = node("ol");
    for (const step of [
      "Publish the public church profile with the correct country and denomination.",
      "The person creates their own member account and discovers this church.",
      "They select Request to join; the request appears in this administrator inbox.",
      "Verify their identity before approving or linking an existing member.",
    ]) steps.append(node("li", step));
    guide.append(steps);

    const links = node("div");
    links.className = "membership-onboarding-actions";
    if (!profilePublished) {
      const jump = node("button", "Set up public profile");
      jump.type = "button";
      jump.className = "membership-guide-button";
      jump.addEventListener("click", () => {
        $("publicChurchForm").scrollIntoView({ behavior: "smooth", block: "start" });
        $("publicChurchForm").querySelector('[name="country"]')?.focus({ preventScroll: true });
      });
      links.append(jump);
    }
    links.append(
      memberLink("Open member registration", "/member/account.html"),
      memberLink("Open church discovery", "/member/discover.html"),
    );
    guide.append(links);
  };

  const updateEmptyState = () => {
    const empty = $("networkRequests").querySelector(".membership-empty-state");
    if (!empty) return;
    const current = $("networkRequestStatus").value;
    empty.replaceChildren();
    empty.append(
      node(
        "strong",
        current === "pending" ? "No pending membership requests yet." : "No requests with this status.",
      ),
    );
    if (current === "pending") {
      empty.append(
        node(
          "p",
          profilePublished === false
            ? "Publish the church profile below before asking a member to find this church and request to join."
            : "A member must create an account and select Request to join from the church directory. This inbox will then show their request.",
        ),
      );
    }
  };
  renderGuide();

  const updatePending = (items) => {
    const currentIds = new Set(items.map((item) => item.id));
    if (knownPendingIds === null) {
      // Show requests that already exist on the first administrator login.
      if (currentIds.size) {
        notify(currentIds.size === 1
          ? "1 membership request is waiting for review."
          : currentIds.size + "+ membership requests are waiting for review.", "info");
      }
    } else {
      const newCount = items.filter((item) => !knownPendingIds.has(item.id)).length;
      if (newCount) {
        notify(newCount === 1
          ? "New membership request received."
          : newCount + " new membership requests received.", "info");
      }
    }
    knownPendingIds = currentIds;
  };
  const pollPending = async () => {
    // Bounded polling works only for a visible, signed-in staff browser tab.
    if (pollInFlight || document.hidden || !state.auth?.access_token || $("appShell").hidden) return;
    pollInFlight = true;
    try {
      const data = await fetchJson("/network/admin/requests?status=pending&offset=0");
      if (!document.hidden && Array.isArray(data.items)) updatePending(data.items);
    } catch (_) {
      // A transient polling failure must not interrupt other staff work.
    } finally {
      pollInFlight = false;
    }
  };
  const startPolling = () => {
    if (pollingStarted) return;
    pollingStarted = true;
    window.setInterval(pollPending, 30000);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) pollPending();
    });
  };

  const requests = async (append = false) => {
    const data = await fetchJson(
      "/network/admin/requests?status=" +
        $("networkRequestStatus").value +
        "&offset=" +
        offset,
    );
    if (!append && offset === 0 && $("networkRequestStatus").value === "pending") {
      updatePending(data.items);
    }
    const list = $("networkRequests");
    if (!append) list.replaceChildren();
    if (!data.items.length && !offset) {
      const empty = node("div");
      empty.className = "membership-empty-state";
      list.append(empty);
      updateEmptyState();
    }
    for (const r of data.items) {
      const card = node("article");
      card.className = "request-card";
      const p = r.applicant_snapshot || {};
      if (p.avatar_url?.startsWith("https://")) {
        const image = node("img");
        image.src = p.avatar_url;
        image.alt = "";
        image.referrerPolicy = "no-referrer";
        card.append(image);
      }
      card.append(
        node("h3", p.name || "VINYRD applicant"),
        node(
          "p",
          new Date(r.created_at).toLocaleString() +
            " · " +
            r.status.replaceAll("_", " "),
        ),
        node(
          "p",
          [p.email, p.phone].filter(Boolean).join(" · ") ||
            "Contact details not shared.",
        ),
        node("p", r.message || "No introduction provided."),
      );
      if (r.rejection_reason)
        card.append(node("p", "Reviewer note: " + r.rejection_reason));
      if (["pending", "more_info_required"].includes(r.status)) {
        const label = node(
          "label",
          "Link existing member (verify identity first)",
        );
        const select = node("select");
        select.append(new Option("Create a new church member", ""));
        r.possible_matches.forEach((m) =>
          select.append(
            new Option(
              [m.name, m.email, m.phone, m.id].filter(Boolean).join(" · "),
              m.id,
            ),
          ),
        );
        label.append(select);
        const verified = node("input");
        verified.type = "checkbox";
        const confirmation = node(
          "label",
          "I verified that the selected existing member is this applicant.",
        );
        confirmation.prepend(verified);
        const note = node("textarea");
        note.maxLength = 2000;
        note.setAttribute("aria-label", "Reviewer note or rejection reason");
        note.placeholder = "Optional note or reason (visible to applicant)";
        card.append(label, confirmation, note);
        for (const [title, result] of [
          ["Approve / link selected member", "approved"],
          ["Reject", "rejected"],
          ["Request more information", "more_info_required"],
        ]) {
          card.append(
            action(title, async () => {
              if (result === "approved" && select.value && !verified.checked)
                throw new Error(
                  "Verify the existing member identity and tick the confirmation before linking.",
                );
              await sendJson("/identity/requests/" + r.id + "/review", "POST", {
                status: result,
                matched_member_id:
                  result === "approved" ? select.value || null : null,
                reason: note.value || null,
              });
              const confirmations = {
                approved: "Membership approved.",
                rejected: "Membership request rejected.",
                more_info_required: "More information requested.",
              };
              const confirmation = confirmations[result] || "Request updated.";
              status(confirmation);
              notify(confirmation);
              // Confirm immediately after the server accepts the review; refreshing
              // the inbox is a separate read and must not swallow the success bubble.
              offset = 0;
              try {
                await requests();
              } catch (error) {
                status(confirmation + " Refresh failed: " + error.message);
              }
            }),
          );
        }
      }
      list.append(card);
    }
    $("networkRequestsMore").hidden = !data.has_more;
  };
  const profile = async () => {
    const [data, denominationData] = await Promise.all([
      fetchJson("/network/admin/profile"),
      fetchJson("/network/denominations"),
    ]);
    profilePublished = Boolean(data.is_published);
    renderGuide();
    updateEmptyState();
    const form = $("publicChurchForm");
    form.replaceChildren();
    const fields = [
      ["name", "Church name", 160],
      ["country", "Country code", 2],
      ["region", "Region", 100],
      ["city", "City", 100],
      ["location", "Public location", 240],
      ["logo_url", "Logo HTTPS URL", 2048],
      ["about", "About", 6000],
      ["service_times", "Service times", 2000],
      ["contact_email", "Public email", 255],
      ["contact_phone", "Public phone", 40],
      ["website", "Website HTTPS URL", 2048],
    ];
    for (const [key, title, max] of fields) {
      const label = node("label", title);
      const input = node(
        ["about", "service_times"].includes(key) ? "textarea" : "input",
      );
      input.name = key;
      input.maxLength = max;
      input.value = data[key] || "";
      input.required = ["name", "country"].includes(key);
      if (key === "country") input.pattern = "[A-Za-z]{2}";
      if (["logo_url", "website"].includes(key)) input.type = "url";
      label.append(input);
      form.append(label);
    }

    const denominationGroup = node("fieldset");
    denominationGroup.append(node("legend", "Denomination & church structure"));
    const denominationLabel = node("label", "Denomination");
    const denominationSelect = node("select");
    denominationSelect.name = "denomination_choice";
    denominationSelect.append(new Option("Choose denomination", ""));
    denominationData.items.forEach((option) =>
      denominationSelect.append(new Option(option.label, option.value)),
    );
    denominationSelect.append(new Option("Other / custom denomination", "__other__"));
    denominationLabel.append(denominationSelect);

    const denominationOtherLabel = node("label", "Other denomination");
    const denominationOther = node("input");
    denominationOther.name = "denomination_other";
    denominationOther.maxLength = 120;
    denominationOtherLabel.append(denominationOther);

    const architecture = node("div");
    architecture.className = "denomination-architecture";
    const renderArchitecture = () => {
      const selected = denominationData.items.find(
        (option) => option.value === denominationSelect.value,
      );
      denominationOtherLabel.hidden = denominationSelect.value !== "__other__";
      architecture.replaceChildren();
      if (selected) {
        architecture.append(
          node("strong", selected.label + " default structure"),
          node(
            "p",
            selected.levels
              .map((level) =>
                level.optional ? level.label + " (optional)" : level.label,
              )
              .join(" → "),
          ),
        );
        selected.levels.forEach((level) => {
          const row = node("p");
          const heading = node(
            "strong",
            (level.optional ? level.label + " (optional)" : level.label) + ": ",
          );
          row.append(
            heading,
            document.createTextNode(
              level.positions.map((position) => position.title).join(" · "),
            ),
          );
          architecture.append(row);
        });
        architecture.append(
          node(
            "p",
            "Office titles are denomination-aware display names. VINYRD keeps the underlying permission profile separate for security.",
          ),
        );
      } else if (denominationSelect.value === "__other__") {
        architecture.append(
          node(
            "p",
            "Custom denomination selected. Its hierarchy can be configured when the denomination is onboarded.",
          ),
        );
      }
    };

    const knownDenomination = denominationData.items.find(
      (option) =>
        option.value.toLowerCase() === String(data.denomination || "").toLowerCase() ||
        (option.aliases || []).some(
          (alias) => alias.toLowerCase() === String(data.denomination || "").toLowerCase(),
        ),
    );
    if (knownDenomination) denominationSelect.value = knownDenomination.value;
    else if (data.denomination) {
      denominationSelect.value = "__other__";
      denominationOther.value = data.denomination;
    }
    denominationSelect.addEventListener("change", renderArchitecture);
    denominationGroup.append(
      denominationLabel,
      denominationOtherLabel,
      architecture,
    );
    form.append(denominationGroup);
    renderArchitecture();

    const collections = {};
    for (const [key, title] of [
      ["public_events", "Public events"],
      ["public_announcements", "Public announcements"],
      ["public_ministries", "Public ministries"],
    ]) {
      const group = node("fieldset");
      group.append(node("legend", title));
      const rows = node("div");
      collections[key] = rows;
      const add = (item = {}) => {
        const row = node("fieldset");
        for (const [name, label] of [
          ["title", "Title"],
          ["body", "Details"],
          ["starts_at", "Date and time (optional)"],
          ["location", "Location (optional)"],
        ]) {
          const wrapper = node("label", label);
          const input = node(name === "body" ? "textarea" : "input");
          input.dataset.field = name;
          input.value =
            name === "starts_at" && item[name]
              ? new Date(
                  new Date(item[name]).getTime() -
                    new Date(item[name]).getTimezoneOffset() * 60000,
                )
                  .toISOString()
                  .slice(0, 16)
              : item[name] || "";
          input.required = name === "title";
          if (name === "starts_at") input.type = "datetime-local";
          else
            input.maxLength =
              name === "title" ? 160 : name === "body" ? 2000 : 240;
          wrapper.append(input);
          row.append(wrapper);
        }
        row.append(action("Remove item", () => row.remove()));
        rows.append(row);
      };
      (data[key] || []).forEach(add);
      group.append(
        rows,
        action("Add " + title.toLowerCase(), () => {
          if (rows.children.length >= 50)
            throw new Error("Maximum 50 items per section.");
          add();
        }),
      );
      form.append(group);
    }
    const label = node("label", "Publish this profile for everyone to see");
    const published = node("input");
    published.type = "checkbox";
    published.checked = data.is_published;
    label.prepend(published);
    form.append(label);
    const save = node("button", "Save public profile");
    save.type = "submit";
    form.append(save);
    form.onsubmit = async (event) => {
      event.preventDefault();
      save.disabled = true;
      try {
        const payload = {};
        fields.forEach(
          ([key]) => (payload[key] = form.elements[key].value.trim() || null),
        );
        payload.denomination =
          denominationSelect.value === "__other__"
            ? denominationOther.value.trim() || null
            : denominationSelect.value || null;
        payload.is_published = published.checked;
        for (const [key, rows] of Object.entries(collections))
          payload[key] = Array.from(rows.children, (row) => {
            const item = {};
            row
              .querySelectorAll("[data-field]")
              .forEach(
                (input) =>
                  (item[input.dataset.field] =
                    input.dataset.field === "starts_at"
                      ? input.value
                        ? new Date(input.value).toISOString()
                        : null
                      : input.value),
              );
            return item;
          });
        await sendJson("/network/admin/profile", "PUT", payload);
        profilePublished = published.checked;
        renderGuide();
        updateEmptyState();
        status(
          published.checked
            ? "Public church profile published."
            : "Draft saved. This church profile is hidden from discovery.",
        );
      } catch (e) {
        status(e.message);
      } finally {
        save.disabled = false;
      }
    };
  };
  $("networkRequestStatus").addEventListener("change", () => {
    offset = 0;
    requests().catch((e) => status(e.message));
  });
  $("networkRefresh").addEventListener("click", () => {
    offset = 0;
    requests().catch((e) => status(e.message));
  });
  $("networkRequestsMore").addEventListener("click", async (event) => {
    event.target.disabled = true;
    offset += 50;
    try {
      await requests(true);
    } catch (e) {
      offset -= 50;
      status(e.message);
    } finally {
      event.target.disabled = false;
    }
  });
  window.VinyrdNetworkAdmin = {
    load: async () => {
      offset = 0;
      await Promise.all([requests(), profile(), state.staffContext?.local_access ? window.VinyrdOrganizationAdmin.load() : Promise.resolve()]);
      startPolling();
      if (state.staffContext && !state.staffContext.local_access) document.getElementById("organizationSetup").textContent = "Use Organization Administration for scoped offices and access. Initial church setup remains local.";
    },
  };
})();
