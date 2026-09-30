(() => {
  const api = "/network/admin/organization/governance";
  const node = (tag, text) => { const e = document.createElement(tag); if (text != null) e.textContent = text; return e; };
  async function load(root) {
    const generation = Symbol(); root.generation = generation;
    const current = () => root.isConnected && root.generation === generation;
    root.replaceChildren(node("h3", "Template Governance"));
    const status = node("p"); status.setAttribute("role", "status"); root.append(status);
    const button = (text, run) => {
      const b = node("button", text); b.type = "button";
      b.onclick = async () => { b.disabled = true; try { await run(); } catch (e) { if (current()) status.textContent = e.message; } finally { b.disabled = false; } };
      return b;
    };
    const field = (parent, title, tag = "input") => {
      const label = node("label", title), input = node(tag); input.setAttribute("aria-label", title);
      label.append(input); parent.append(label); return input;
    };
    try {
      const [data, history] = await Promise.all([fetchJson(api), fetchJson(api + "/history")]);
      if (!current()) return;
      root.append(node("p", `${data.denomination} · Installed: ${data.installed_version ?? "Custom"} · Available: ${data.available_version ?? "Custom configuration required"} · ${data.compatibility_status}`));
      root.append(node("p", "Approval applies only to this church. Shared ancestor changes require independent review. Offices and access grants are not changed."));
      for (const [key, labels] of Object.entries(data.overrides || {})) root.append(node("p", `Approved local override ${key}: ${Object.entries(labels).map(([locale,value]) => locale + ": " + value).join(" / ")}`));
      if (data.compatibility_status !== "requires_configuration") {
        const version = field(root, "Destination template version", "select");
        for (const v of data.versions.length ? data.versions : [null]) { const option = node("option", v ?? "Installed custom template"); option.value = v ?? ""; version.append(option); }
        version.value = data.available_version ?? "";
        const form = node("div"); form.className = "network-form";
        root.append(node("h4", "Local terminology override"), node("p", "Optional: select a level or office and supply approved labels. Leave labels blank to keep them; reset removes the local override. Provenance: church_approved."), form);
        const level = field(form, "Organization level for override", "select"), position = field(form, "Office for override", "select");
        const option = (select, value, text) => { const o = node("option", text); o.value = value; select.append(o); };
        const term = row => row.presentation?.[data.locale || "en"]?.bilingual_label || row.label || row.title || row.key;
        option(level, "", "No local override");
        for (const item of data.runtime_levels) option(level, item.key, term(item));
        const offices = () => { position.replaceChildren(); option(position, "", "Level terminology"); for (const office of data.runtime_levels.find(l => l.key === level.value)?.positions || []) option(position, office.key, term(office)); };
        level.addEventListener("change", offices); offices();
        const english = field(form, "Approved English label"), swahili = field(form, "Approved Kiswahili label");
        const reset = field(form, "Reset local override"); reset.type = "checkbox";
        const comparison = node("section"); root.append(comparison);
        let reviewed = null;
        const proposal = () => ({target_version: version.value ? Number(version.value) : null, overrides: level.value.trim() ? [{
          level_key: level.value.trim(), position_key: position.value.trim() || null,
          labels: reset.checked ? {en:null, sw:null} : {...(english.value.trim() ? {en:english.value.trim()} : {}), ...(swahili.value.trim() ? {sw:swahili.value.trim()} : {})}
        }] : []});
        const approve = button("Approve reviewed changes", async () => {
          if (!reviewed || JSON.stringify(proposal()) !== reviewed.input) throw new Error("Inputs changed. Review again.");
          await sendJson(api + "/approve", "POST", {...reviewed.payload, expected_revision:reviewed.data.revision, preview_token:reviewed.data.preview_token, request_id:reviewed.requestId});
          if (current()) { await load(root); window.VinyrdOrganizationAccess?.load(); }
        }); approve.hidden = true;
        const invalidate = () => { reviewed = null; approve.hidden = true; comparison.replaceChildren(); };
        for (const input of [version, level, position, english, swahili, reset]) input.addEventListener("input", invalidate);
        root.append(button("Review upgrade", async () => {
          const payload = proposal(), input = JSON.stringify(payload);
          const result = await sendJson(api + "/preview", "POST", payload);
          if (!current() || JSON.stringify(proposal()) !== input) return;
          reviewed = {payload, input, data:result, requestId:crypto.randomUUID()}; comparison.replaceChildren();
          status.textContent = result.compatibility_status;
          comparison.append(node("h4", "Current and proposed terminology"), node("p", `Template provenance: ${result.provenance.template}; local overrides: ${result.provenance.overrides}; approval: ${result.approval_status}`));
          for (const problem of result.problems) comparison.append(node("p", problem));
          const locale = data.locale || "en";
          for (const [heading, rows] of [["Hierarchy changes",result.levels],["Office changes",result.positions]]) {
            comparison.append(node("h4", heading));
            for (const row of rows) {
              const label = value => { const labels = value?.labels || {}; const order = locale === "sw" ? ["sw","en"] : ["en","sw"]; return order.map(l => `${l}: ${labels[l] || labels.en || "—"}`).join(" / "); };
              const line = node("p", `${row.level_key ? row.level_key + " / " : ""}${row.key}: ${label(row.current)} → ${label(row.proposed)} · ${row.status}`);
              line.append(node("span", ` · Provenance: ${row.current?.provenance || "installed snapshot"} → ${row.proposed?.provenance || result.provenance.template}`));
              if (row.canonical_identifier_changed || row.structural_change) line.append(node("strong", " Structural/identifier change"));
              if (row.kind === "position") line.append(node("span", ` · Permission suggestion: ${row.current?.permission_role || "—"} → ${row.proposed?.permission_role || "—"} (no access change)`));
              comparison.append(line);
            }
          }
          comparison.append(node("h4", "Publication impact"));
          for (const item of result.publication) comparison.append(node("p", `${item.level_key}: ${item.impact} · ${item.status}`));
          approve.hidden = result.compatibility_status !== "compatible";
        }), approve);
      }
      root.append(node("h4", "Upgrade history"));
      for (const row of history.items) root.append(node("p", `${row.before.template_version ?? "Custom"} → ${row.after.template_version ?? "Custom"} · ${row.approved_at} · Approved by ${row.approved_by} · ${row.compatibility_status}`));
      if (!history.items.length) root.append(node("p", "No approved template changes."));
    } catch (e) { if (current()) status.textContent = e.message.includes("403")
      ? "Only this church's local administrator can govern its configuration. Switch to your local church."
      : e.message.includes("409") ? "Configure this church's organization before reviewing templates." : e.message; }
  }
  window.VinyrdTemplateGovernance = {load};
})();
