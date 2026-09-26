(async () => {
  const page = document.body.dataset.networkPage;
  const content = document.querySelector("#networkContent");
  const status = document.querySelector("#networkStatus");
  const churchId = new URLSearchParams(location.search).get("id");
  let mine = { memberships: [], requests: [], follows: [] };
  let offset = 0;
  let refreshTimer;
  const el = (tag, value, className) => {
    const node = document.createElement(tag);
    if (value != null) node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  const link = (text, href) => {
    const node = el("a", text, "network-button secondary");
    node.href = href;
    return node;
  };
  const button = (text, action) => {
    const node = el("button", text, "network-button");
    node.type = "button";
    node.addEventListener("click", async () => {
      node.disabled = true;
      status.textContent = "Saving…";
      try {
        await action();
        status.textContent = "Saved.";
        await loadMine();
        await render();
      } catch (error) {
        status.textContent = error.message;
      } finally {
        node.disabled = false;
      }
    });
    return node;
  };
  const api = (path, method, payload) =>
    VinyrdClient.apiRequest(path, {
      method,
      ...(payload ? { body: JSON.stringify(payload) } : {}),
    });
  const loadMine = async () => {
    if (!VinyrdClient.token()) return;
    await api("/network/me/initialize-home", "POST");
    mine = await VinyrdClient.apiRequest("/network/me");
  };
  const card = (church) => {
    const node = el("article", null, "network-card");
    if (church.logo_url?.startsWith("https://")) {
      const image = el("img");
      image.src = church.logo_url;
      image.alt = "";
      image.className = "network-logo";
      image.referrerPolicy = "no-referrer";
      node.append(image);
    }
    node.append(
      el("h2", church.name),
      el(
        "p",
        [church.city, church.region, church.country]
          .filter(Boolean)
          .join(" · "),
      ),
    );
    if (church.denomination) node.append(el("p", church.denomination));
    node.append(
      link(
        "View church",
        "./church.html?id=" + encodeURIComponent(church.church_id),
      ),
    );
    return node;
  };
  const renderChurch = async () => {
    const church = await VinyrdClient.publicRequest(
      "/network/churches/" + encodeURIComponent(churchId || ""),
    );
    content.replaceChildren();
    const main = card(church);
    main.querySelector("a").remove();
    if (church.about) main.append(el("p", church.about));
    if (church.location) main.append(el("p", church.location));
    if (church.service_times)
      main.append(el("h3", "Service times"), el("p", church.service_times));
    for (const [title, key] of [
      ["Public events", "public_events"],
      ["Public announcements", "public_announcements"],
      ["Public ministries", "public_ministries"],
    ]) {
      if (church[key].length) main.append(el("h3", title));
      for (const item of church[key])
        main.append(
          el("h4", item.title),
          el(
            "p",
            [
              item.body,
              item.starts_at ? new Date(item.starts_at).toLocaleString() : "",
              item.location,
            ]
              .filter(Boolean)
              .join("\n"),
          ),
        );
    }
    if (church.contact_email || church.contact_phone || church.website) {
      main.append(
        el("h3", "Public contact"),
        el(
          "p",
          [church.contact_email, church.contact_phone]
            .filter(Boolean)
            .join(" · "),
        ),
      );
      if (church.website?.startsWith("https://")) {
        const site = link("Church website", church.website);
        site.rel = "noopener noreferrer";
        main.append(site);
      }
    }
    content.append(main);
    if (!VinyrdClient.token()) {
      main.append(link("Sign in to follow or request to join", "./login.html"));
      return;
    }
    const actions = el("section", null, "network-card");
    const following = mine.follows.includes(churchId);
    actions.append(
      el("h2", "Follow this church"),
      el(
        "p",
        "Stay connected to public updates. Following does not make you a church member.",
      ),
      button(following ? "Unfollow" : "Follow", () =>
        api(
          `/identity/churches/${churchId}/follow`,
          following ? "DELETE" : "PUT",
        ),
      ),
    );
    content.append(actions);
    const join = el("section", null, "network-card");
    join.append(el("h2", "Church membership"));
    const membership = mine.memberships.find((m) => m.church_id === churchId);
    const request = mine.requests.find((r) => r.church_id === churchId);
    if (membership?.status === "active") {
      join.append(
        el("p", "Approved member"),
        button("View My Church", async () => {
          VinyrdClient.setViewedChurch(churchId);
          location.href = "./my-church.html";
        }),
      );
    } else if (membership?.status === "suspended") {
      join.append(el("p", "Membership suspended. Contact the church office."));
    } else if (
      request &&
      ["pending", "more_info_required"].includes(request.status)
    ) {
      join.append(
        el(
          "p",
          request.status === "pending"
            ? "Membership request pending review."
            : "More information requested.",
        ),
      );
      if (request.rejection_reason)
        join.append(el("p", request.rejection_reason));
      join.append(
        button("Cancel request", () =>
          api(`/identity/requests/${request.id}/cancel`, "POST"),
        ),
      );
      if (request.status === "more_info_required")
        join.append(
          el(
            "p",
            "Contact the church, or cancel and submit a new request with more details.",
          ),
        );
    } else {
      if (request?.status === "rejected")
        join.append(
          el(
            "p",
            "Previous request rejected. " +
              (request.rejection_reason ||
                "Your VINYRD account and follows are unchanged."),
          ),
        );
      const form = el("form", null, "network-form");
      const message = el("textarea");
      message.maxLength = 2000;
      message.placeholder = "Introduce yourself (optional)";
      message.setAttribute("aria-label", "Membership request message");
      const consent = el("label");
      const checkbox = el("input");
      checkbox.type = "checkbox";
      consent.append(
        checkbox,
        document.createTextNode(
          " Share my email, phone and profile photo with this church's request reviewers. My name and message are always shared.",
        ),
      );
      const submit = el("button", "Request to join", "network-button");
      submit.type = "submit";
      form.append(message, consent, submit);
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        submit.disabled = true;
        try {
          await api(`/identity/churches/${churchId}/requests`, "POST", {
            message: message.value || null,
            share_contact: checkbox.checked,
          });
          await loadMine();
          await renderChurch();
          status.textContent =
            "Request sent. Membership remains pending until approved.";
        } catch (error) {
          status.textContent = error.message;
        } finally {
          submit.disabled = false;
        }
      });
      join.append(
        el(
          "p",
          "Request membership separately from following. The church will review your request.",
        ),
        form,
      );
    }
    content.append(join);
  };
  const renderList = async () => {
    const form = document.querySelector("#discoverForm");
    const params = new URLSearchParams(new FormData(form));
    if (params.get("denomination") === "__other__")
      params.set("denomination", params.get("denomination_custom") || "");
    params.delete("denomination_custom");
    params.set("offset", String(offset));
    const data = await VinyrdClient.publicRequest(
      "/network/churches?" + params,
    );
    if (!offset) content.replaceChildren();
    data.items.forEach((church) => content.append(card(church)));
    if (!data.items.length && !offset)
      content.append(
        el(
          "p",
          "No published churches match these filters. Try a broader location or check back later.",
        ),
      );
    document.querySelector("#moreChurches").hidden = !data.has_more;
  };
  const renderFollowing = async () => {
    content.replaceChildren();
    if (!mine.follows.length) {
      content.append(
        el("p", "You aren't following any churches yet."),
        link("Discover churches", "./discover.html"),
      );
      return;
    }
    for (const id of mine.follows) {
      let node;
      try {
        node = card(
          await VinyrdClient.publicRequest("/network/churches/" + id),
        );
      } catch (error) {
        if (error.status !== 404) throw error;
        node = el(
          "article",
          "This church's public profile is currently unavailable.",
          "network-card",
        );
      }
      node.append(
        button("Unfollow", () =>
          api(`/identity/churches/${id}/follow`, "DELETE"),
        ),
      );
      content.append(node);
    }
  };
  const renderMyChurch = async () => {
    content.replaceChildren();
    const active = mine.memberships.filter((m) => m.status === "active");
    if (!active.length) {
      content.append(
        el(
          "p",
          "You have no approved active memberships yet. You can still discover and follow churches.",
        ),
        link("Discover churches", "./discover.html"),
      );
    }
    for (const membership of active) {
      const node = el("article", null, "network-card");
      node.append(
        el("h2", membership.church_name),
        el("p", membership.is_primary ? "Home Church" : "Active membership"),
      );
      node.append(
        button("View this church", async () => {
          VinyrdClient.setViewedChurch(membership.church_id);
          location.reload();
        }),
      );
      if (!membership.is_primary)
        node.append(
          button("Make Home Church", () =>
            api(`/identity/memberships/${membership.id}/primary`, "PUT"),
          ),
        );
      content.append(node);
    }
    if (active.length) {
      const selected =
        active.find((m) => m.church_id === VinyrdClient.viewedChurch()) ||
        active.find((m) => m.is_primary) ||
        active[0];
      VinyrdClient.setViewedChurch(selected.church_id);
      const panel = el("section", null, "network-card");
      panel.append(
        el("h2", "Viewing " + selected.church_name),
        el(
          "p",
          "Viewing a church does not change Home Church. Changing Home Church never leaves other memberships.",
        ),
      );
      const actions = el("div", null, "network-actions");
      for (const [title, path] of [
        ["Overview", "home"],
        ["Giving", "giving"],
        ["Attendance & events", "events"],
        ["Groups", "groups"],
        ["Messages", "messages"],
        ["Prayers", "prayers"],
      ])
        actions.append(link(title, `./${path}.html`));
      panel.append(actions);
      content.prepend(panel);
    }
    if (mine.requests.length) {
      const history = el("section", null, "network-card");
      history.append(el("h2", "Your membership requests"));
      mine.requests.forEach((r) => {
        const row = el(
          "p",
          r.status.replaceAll("_", " ") +
            (r.rejection_reason ? " · " + r.rejection_reason : ""),
        );
        row.append(" ", link("View church", "./church.html?id=" + r.church_id));
        history.append(row);
      });
      content.append(history);
    }
  };
  const render = async () => {
    if (page === "church") await renderChurch();
    if (page === "discover") await renderList();
    if (page === "following") await renderFollowing();
    if (page === "my-church") await renderMyChurch();
  };
  if (
    ["following", "my-church"].includes(page) &&
    !VinyrdClient.requireSession()
  )
    return;
  if (page === "discover") {
    const denominationSelect = document.querySelector("#denominationSelect");
    const customDenominationLabel = document.querySelector(
      "#customDenominationLabel",
    );
    const denominationArchitecture = document.querySelector(
      "#denominationArchitecture",
    );
    try {
      const denominationData =
        await VinyrdClient.publicRequest("/network/denominations");
      denominationData.items.forEach((option) =>
        denominationSelect.append(new Option(option.label, option.value)),
      );
      denominationSelect.append(
        new Option("Other / custom denomination", "__other__"),
      );
      const renderDenominationArchitecture = () => {
        const selected = denominationData.items.find(
          (option) => option.value === denominationSelect.value,
        );
        customDenominationLabel.hidden =
          denominationSelect.value !== "__other__";
        if (selected) {
          denominationArchitecture.replaceChildren();
          denominationArchitecture.append(
            el(
              "strong",
              selected.label +
                ": " +
                selected.levels
                  .map((level) =>
                    level.optional ? level.label + " (optional)" : level.label,
                  )
                  .join(" → "),
            ),
          );
          selected.levels.forEach((level) => {
            denominationArchitecture.append(
              el(
                "span",
                level.label +
                  ": " +
                  level.positions.map((position) => position.title).join(" · "),
              ),
            );
          });
        } else {
          denominationArchitecture.textContent =
            denominationSelect.value === "__other__"
              ? "Custom denomination: its hierarchy and office titles can be configured during onboarding."
              : "";
        }
      };
      denominationSelect.addEventListener(
        "change",
        renderDenominationArchitecture,
      );
      renderDenominationArchitecture();
    } catch (error) {
      denominationArchitecture.textContent =
        "Denomination templates are temporarily unavailable. You can still search by church name or location.";
    }
    document
      .querySelector("#discoverForm")
      .addEventListener("submit", async (event) => {
        event.preventDefault();
        offset = 0;
        status.textContent = "Searching…";
        try {
          await renderList();
          status.textContent = "Search complete.";
        } catch (error) {
          status.textContent = error.message;
        }
      });
    document
      .querySelector("#moreChurches")
      .addEventListener("click", async (event) => {
        event.target.disabled = true;
        offset += 24;
        try {
          await renderList();
        } catch (error) {
          offset -= 24;
          status.textContent = error.message;
        } finally {
          event.target.disabled = false;
        }
      });
  }
  try {
    await loadMine();
    await render();
    status.textContent = "";
  } catch (error) {
    status.textContent = error.message;
  }
  if (["church", "my-church"].includes(page) && VinyrdClient.token()) {
    refreshTimer = setInterval(async () => {
      if (document.hidden || document.activeElement?.closest("form")) return;
      try {
        const before = JSON.stringify(mine);
        await loadMine();
        if (before !== JSON.stringify(mine)) await render();
      } catch (error) {
        status.textContent = error.message;
      }
    }, 30000);
    window.addEventListener("pagehide", () => clearInterval(refreshTimer), {
      once: true,
    });
  }
})();
