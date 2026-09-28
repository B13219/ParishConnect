/* Organization setup is an explicit confirmation, independent of public profiles. */
(() => {
  const root = document.getElementById("organizationSetup");
  const api = "/network/admin/organization";
  const node = (tag, text) => {
    const el = document.createElement(tag);
    if (text != null) el.textContent = text;
    return el;
  };
  const bilingual = (item) => [...new Set([item.labels?.sw, item.labels?.en].filter(Boolean))].join(" / ") || item.key;
  const option = (select, value, text) => {
    const item = node("option", text);
    item.value = value;
    select.append(item);
  };
  const field = (parent, title, name, kind = "text") => {
    const label = node("label", title);
    const input = node(kind === "select" ? "select" : "input");
    if (kind !== "select") input.type = kind;
    input.name = name;
    input.setAttribute("aria-label", title);
    label.append(input);
    parent.append(label);
    return input;
  };
  const button = (parent, title, handler) => {
    const el = node("button", title);
    el.type = "button";
    el.addEventListener("click", handler);
    parent.append(el);
    return el;
  };
  let generation = 0;
  const load = async () => {
    const version = ++generation;
    root.replaceChildren(node("p", "Loading organization setup…"));
    try {
      const [config, catalog] = await Promise.all([
        fetchJson(api + "/setup"), fetchJson("/network/denominations"),
      ]);
      if (version !== generation) return;
      root.replaceChildren(node("h2", "Church organization setup"));
      const status = node("p");
      status.id = "organizationStatus";
      status.setAttribute("role", "status");
      root.append(status);
      if (config.setup_status === "configured") {
        status.textContent = "Organization setup configured — " + config.denomination + " (template " + config.template_version + ").";
        const path = node("ol");
        for (const unit of config.organization_path) path.append(node("li", bilingual(unit) + ": " + unit.canonical_name));
        root.append(path, node("p", "This installed snapshot is preserved when templates change. Structural changes require a future configuration workflow."));
        await offices(config, status);
        return;
      }
      status.textContent = config.setup_status === "custom_required"
        ? "Custom configuration required for " + config.denomination + ". No hierarchy has been assumed."
        : "Organization setup incomplete. Existing church operations continue normally.";
      root.append(node("p", "Choose the church's actual structure. Names are official names and are never translated automatically. Preview and review do not save records."));
      const form = node("form");
      form.className = "network-form";
      form.id = "organizationSetupForm";
      const controls = node("fieldset");
      const denomination = field(controls, "Organization denomination", "denomination", "select");
      option(denomination, "", "Choose denomination");
      for (const item of catalog.items) option(denomination, item.value, item.label);
      option(denomination, "__custom", "Other / custom denomination");
      const custom = field(controls, "Official custom denomination name", "custom_denomination");
      custom.maxLength = 120;
      custom.parentElement.hidden = true;
      const level = field(controls, "What level are you setting up?", "organization_level", "select");
      const ancestry = node("div");
      const review = node("div");
      review.id = "organizationReview";
      controls.append(ancestry);
      form.append(controls, review);
      root.append(form);
      let preview = null;
      let requestNumber = 0;
      let rows = [];
      const resetReview = () => review.replaceChildren();
      controls.addEventListener("input", resetReview);
      const refresh = async (resetLevel) => {
        const request = ++requestNumber;
        resetReview();
        preview = null;
        ancestry.replaceChildren();
        rows = [];
        const isCustom = denomination.value === "__custom";
        custom.parentElement.hidden = !isCustom;
        custom.required = isCustom;
        level.parentElement.hidden = isCustom;
        if (!denomination.value || (isCustom && !custom.value.trim())) return;
        const payload = { denomination: isCustom ? custom.value.trim() : denomination.value };
        if (!isCustom && !resetLevel && level.value) payload.organization_level = level.value;
        try {
          const data = await sendJson(api + "/preview", "POST", payload);
          if (request !== requestNumber || version !== generation) return;
          preview = data;
          level.replaceChildren();
          for (const entry of data.levels) option(level, entry.key, bilingual(entry));
          level.value = data.organization_level || "";
          if (isCustom) {
            ancestry.append(node("p", "Custom configuration required. Confirmation saves the denomination name only; no built-in hierarchy will be applied."));
            return;
          }
          ancestry.append(node("p", data.levels.map(bilingual).join(" → ")));
          const active = [...data.expected_parents, data.levels.find((entry) => entry.key === data.organization_level)];
          for (const entry of active) {
            const group = node("fieldset");
            group.append(node("legend", bilingual(entry)));
            let include = null;
            if (entry.optional && entry.key !== data.organization_level) {
              include = field(group, "Include optional " + bilingual(entry), "include_" + entry.key, "checkbox");
            }
            const details = node("div");
            const name = field(details, "Official name — " + bilingual(entry), "name_" + entry.key);
            name.maxLength = 200;
            name.required = !include;
            const country = field(details, "Country code (optional, e.g. TZ)", "country_" + entry.key);
            country.pattern = "[A-Za-z]{2}";
            country.maxLength = 2;
            const region = field(details, "Region (optional)", "region_" + entry.key);
            const city = field(details, "City (optional)", "city_" + entry.key);
            region.maxLength = city.maxLength = 100;
            const published = field(details, "Publish this unit's official name and terminology", "published_" + entry.key, "checkbox");
            if (include) {
              const toggle = () => {
                details.hidden = !include.checked;
                name.required = include.checked;
                details.querySelectorAll("input").forEach((input) => {
                  input.disabled = !include.checked;
                });
              };
              toggle();
              include.addEventListener("change", toggle);
            }
            group.append(details);
            ancestry.append(group);
            rows.push({ entry, include, name, country, region, city, published });
          }
          ancestry.append(node("p", "Public ancestry appears only when every included unit is published. Ancestor records describe affiliation; they grant no authority over other churches."));
        } catch (error) {
          if (request === requestNumber) status.textContent = error.message;
        }
      };
      denomination.addEventListener("change", () => refresh(true));
      custom.addEventListener("change", () => refresh(true));
      level.addEventListener("change", () => refresh(false));
      const reviewButton = button(controls, "Review Church Setup", () => {
        if (!form.reportValidity() || !preview) return;
        const payload = {
          denomination: preview.denomination,
          organization_level: preview.organization_level,
          template_version: preview.template_version,
          units: rows.filter((row) => !row.include || row.include.checked).map((row) => ({
            level_key: row.entry.key, canonical_name: row.name.value.trim(),
            country: row.country.value.trim().toUpperCase() || null,
            region: row.region.value.trim() || null, city: row.city.value.trim() || null,
            is_published: row.published.checked,
          })),
        };
        review.replaceChildren(node("h3", "Review before confirmation"), node("p", payload.denomination + " — template " + (payload.template_version || "custom")));
        const list = node("ol");
        for (const unit of payload.units) {
          const entry = preview.levels.find((item) => item.key === unit.level_key);
          list.append(node("li", bilingual(entry) + ": " + unit.canonical_name + " — " + [unit.country, unit.region, unit.city].filter(Boolean).join(", ") + (unit.is_published ? " (public)" : " (private)")));
        }
        review.append(list, node("p", "Church level: " + (level.selectedOptions[0]?.textContent || "Custom configuration required")), node("p", "Office terminology: " + (preview.available_offices.map(bilingual).join("; ") || "Custom configuration required")), node("p", "Terminology: Kiswahili / English. Office titles do not grant permissions."));
        const confirm = button(review, "Confirm Church Setup", async () => {
          controls.disabled = true;
          confirm.disabled = true;
          try {
            await sendJson(api + "/confirm", "POST", payload);
            await load();
          } catch (error) {
            status.textContent = error.message;
            controls.disabled = false;
            confirm.disabled = false;
          }
        });
      });
      reviewButton.id = "organizationReviewButton";
      form.addEventListener("submit", (event) => event.preventDefault());
      if (config.denomination) {
        denomination.value = catalog.items.some((item) => item.value === config.denomination) ? config.denomination : "__custom";
        custom.value = config.denomination;
        await refresh(true);
      }
    } catch (error) {
      if (version === generation) root.replaceChildren(node("p", error.message));
    }
  };

  async function offices(config, status) {
    const data = await fetchJson(api + "/assignments");
    const local = config.organization_path.at(-1);
    const level = config.hierarchy_snapshot.levels.find((entry) => entry.key === local.level_key);
    const panel = node("div");
    panel.append(node("h3", "Office assignments"), node("p", "Assignments record office and intended permission profile separately. Existing staff access remains controlled by staff roles; these assignments do not grant additional access."));
    const list = node("ul");
    for (const row of data.items) {
      const office = level.positions.find((item) => item.key === row.position_key);
      list.append(node("li", (data.staff.find((item) => item.id === row.user_id)?.name || "Inactive staff") + " — " + (office ? bilingual(office) : row.position_key) + " — " + row.permission_role + " — " + row.status));
    }
    panel.append(list);
    const form = node("form");
    form.className = "network-form";
    const staff = field(form, "Staff user", "staff_user", "select");
    for (const item of data.staff) option(staff, item.id, item.name);
    const office = field(form, "Office title", "position_key", "select");
    for (const item of level.positions) option(office, item.key, bilingual(item));
    const role = field(form, "Intended permission profile (does not grant access)", "permission_role", "select");
    option(role, "", "Choose independently of office title");
    for (const key of data.permission_profiles) option(role, key, key);
    role.required = true;
    const state = field(form, "Assignment status", "assignment_status", "select");
    option(state, "active", "Active");
    option(state, "inactive", "Inactive");
    const save = button(form, "Save office assignment", async () => {
      if (!form.reportValidity()) return;
      save.disabled = true;
      try {
        await sendJson(api + "/assignments", "PUT", {
          organization_unit_id: config.local_unit_id, user_id: staff.value,
          position_key: office.value, permission_role: role.value, status: state.value,
        });
        await load();
      } catch (error) {
        status.textContent = error.message;
        save.disabled = false;
      }
    });
    form.addEventListener("submit", (event) => event.preventDefault());
    panel.append(form);
    root.append(panel);
  }
  window.VinyrdOrganizationAdmin = { load };
})();
