(() => {
  const $ = (id) => document.getElementById(id);
  const node = (tag, text) => {
    const n = document.createElement(tag);
    if (text != null) n.textContent = text;
    return n;
  };
  const status = (text) => ($("networkAdminStatus").textContent = text);
  const action = (label, callback) => {
    const b = node("button", label);
    b.type = "button";
    b.addEventListener("click", async () => {
      b.disabled = true;
      try {
        await callback();
      } catch (e) {
        status(e.message);
      } finally {
        b.disabled = false;
      }
    });
    return b;
  };
  let offset = 0;
  const requests = async (append = false) => {
    const data = await fetchJson(
      "/network/admin/requests?status=" +
        $("networkRequestStatus").value +
        "&offset=" +
        offset,
    );
    const list = $("networkRequests");
    if (!append) list.replaceChildren();
    if (!data.items.length && !offset)
      list.append(node("p", "No requests with this status."));
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
              status("Request updated.");
              offset = 0;
              await requests();
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
      await Promise.all([requests(), profile()]);
    },
  };
})();
