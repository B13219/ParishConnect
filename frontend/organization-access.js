(() => {
  const root = document.getElementById("organization-access");
  const api = "/organization-access";
  const node = (tag, text) => { const e = document.createElement(tag); if (text != null) e.textContent = text; return e; };
  const locale = () => state.staffContext?.locale || state.auth?.user?.ui_language || "en";
  const label = (u) => u.presentation?.[locale()]?.bilingual_label || u.labels?.[locale()] || u.labels?.en || u.level_key;
  const name = (u) => u.presentation?.[locale()]?.name || u.canonical_name;
  const key = () => "vinyrd_staff_branch_" + state.auth.user.id;
  const message = (text) => { root.querySelector('[role="status"]').textContent = text; };
  const button = (text, run) => {
    const b = node("button", text); b.type = "button";
    b.onclick = async () => { b.disabled = true; try { await run(); } catch (e) { message(e.message); } finally { b.disabled = false; } };
    return b;
  };
  const field = (form, text, type, values = []) => {
    const wrap = node("label", text), input = node(type === "select" ? "select" : "input");
    input.setAttribute("aria-label", text);
    if (type !== "select") { input.type = type; input.required = true; }
    for (const [value, text] of values) { const opt = node("option", text); opt.value = value; input.append(opt); }
    wrap.append(input); form.append(wrap); return input;
  };
  let selectedUnit = null;
  let generation = 0;
  async function load() {
    if (!state.auth?.access_token) return;
    const loadVersion = ++generation;
    const data = await fetchJson(api + "/tree");
    if (loadVersion !== generation) return;
    const stored = sessionStorage.getItem(key());
    const selected = data.branches.find(b => b.id === stored) || (!stored && data.branches.find(b => b.local_access));
    if (stored && stored !== "overview" && !selected) {
      sessionStorage.removeItem(key());
      if (state.staffContext?.id) { location.reload(); return; }
    }
    state.staffContext = selected || {roles: [], local_access: false};
    applyRoleAccess();
    let header = document.getElementById("staffOrganizationContext");
    if (!header) { header = node("div"); header.id = "staffOrganizationContext"; document.querySelector("#topbarUserName").parentElement.append(header); }
    header.replaceChildren(node("strong", selected?.name || "Organization overview"));
    for (const u of (selected?.organization_path || []).slice(-3).reverse()) {
      const view = u.presentation?.[locale()];
      if (view) header.append(node("div", view.name + " — " + view.bilingual_label));
    }
    root.replaceChildren(node("h2", "Organization Administration"), node("p", "Office titles and VINYRD access are managed separately. Viewing a church does not change Home Church or membership."));
    const status = node("p"); status.setAttribute("role", "status"); root.append(status);
    root.append(button("Refresh organization access", load));
    const contextForm = node("div"); root.append(contextForm);
    const branch = field(contextForm, "Current church context", "select", [["", "Organization overview"], ...data.branches.map(b => [b.id, b.name])]);
    branch.value = selected?.id || "";
    branch.onchange = async () => {
      try {
        if (branch.value) {
          await sendJson(api + "/context", "POST", {branch_id: branch.value});
          sessionStorage.setItem(key(), branch.value);
        } else sessionStorage.setItem(key(), "overview");
        // Full page reset prevents cached personal/financial data crossing contexts.
        location.reload();
      } catch (e) { message(e.message); await load(); }
    };
    const tree = node("ul"); tree.setAttribute("aria-label", "Authorized organization tree");
    const children = new Map();
    for (const u of data.units) { const list = children.get(u.parent_id) || []; list.push(u); children.set(u.parent_id, list); }
    const queue = [[null, tree]], seen = new Set();
    while (queue.length) {
      const [parent, list] = queue.shift();
      for (const u of children.get(parent) || []) {
        if (seen.has(u.id)) continue; seen.add(u.id);
        const item = node("li", `${label(u)}: ${name(u)}`), sub = node("ul");
        item.append(sub); list.append(item); queue.push([u.id, sub]);
      }
    }
    root.append(tree);
    const select = field(root, "Organization context", "select", data.units.map(u => [u.id, `${label(u)}: ${name(u)}`]));
    if (data.units.some(u => u.id === selectedUnit)) select.value = selectedUnit;
    const details = node("section"); root.append(details);
    const governance = node("section"); governance.id = "templateGovernance"; root.append(governance);
    window.VinyrdTemplateGovernance?.load(governance);
    const [grants, offices] = await Promise.all([fetchJson(api + "/grants"), fetchJson(api + "/offices")]);
    let detailGeneration = 0;
    async function show() {
      const detailVersion = ++detailGeneration;
      selectedUnit = select.value;
      const u = data.units.find(u => u.id === selectedUnit);
      details.replaceChildren();
      if (!u) { details.append(node("p", "No organization access assigned.")); return; }
      details.append(node("h3", name(u)), node("p", `${u.denomination} · ${label(u)}`));
      const parent = data.units.find(p => p.id === u.parent_id);
      details.append(node("p", "Parent: " + ((parent && name(parent)) || "Outside this view / root")));
      const report = await fetchJson(api + "/summary?unit_id=" + encodeURIComponent(u.id));
      if (detailVersion !== detailGeneration || loadVersion !== generation) return;
      details.append(node("h3", label(u) + " Summary"));
      details.append(node("p", `Accessible churches: ${report.accessible_church_count}. Members: ${report.members.count ?? "Not authorized"} (${report.members.church_count} churches). Attendance: ${report.attendance.count ?? "Not authorized"} (${report.attendance.church_count} churches).`));
      if (report.finance) details.append(node("p", `Finance (${report.finance.church_count} churches): ` + report.finance.totals.map(t => `${t.currency} ${t.amount}`).join(", ")));
      details.append(node("h3", "Church offices — no application permissions"));
      for (const o of offices.items.filter(o => o.organization_unit_id === u.id)) {
        const position = u.positions.find(p => p.key === o.position_key);
        const row = node("p", `${o.user.name || o.user.id} · ${position?.presentation?.[locale()]?.bilingual_label || position?.title || o.position_key} · ${o.status}`);
        if (u.can_manage) row.append(button(o.status === "active" ? "Deactivate office" : "Activate office", async () => {
          await sendJson(api + "/offices", "PUT", {user_id:o.user.id,organization_unit_id:u.id,position_key:o.position_key,status:o.status === "active" ? "inactive" : "active"}); await load();
        }));
        details.append(row);
      }
      if (u.can_manage && u.positions.length) {
        const form = node("div"); form.className = "network-form";
        const who = field(form, "Office holder VINYRD account ID", "text");
        const position = field(form, "Church office", "select", u.positions.map(p => [p.key,p.presentation?.[locale()]?.bilingual_label || p.title]));
        form.append(button("Save office only", async () => { await sendJson(api + "/offices", "PUT", {user_id:who.value,organization_unit_id:u.id,position_key:position.value}); await load(); })); details.append(form);
      }
      details.append(node("h3", "VINYRD access grants"));
      const roles = data.permission_profiles.map(r => [r,r.replaceAll("_", " ")]);
      for (const g of grants.items.filter(g => g.organization_unit_id === u.id)) {
        const row = node("div"); row.className = "network-form"; row.dataset.grantUser = g.user.id;
        row.append(node("p", `${g.user.name || g.user.id} · ${g.permission_role} · ${g.scope_mode} · ${g.status}`));
        if (g.can_manage) {
          const role = field(row,"Permission profile", "select", roles); role.value = g.permission_role;
          const mode = field(row,"Access scope", "select", [["unit_only","This unit only"], ...(u.can_manage_descendants ? [["descendants","This unit and descendants"]] : [])]); mode.value = g.scope_mode;
          const status = field(row,"Grant status", "select", ["active","inactive","revoked"].map(v => [v,v])); status.value = g.status;
          row.append(button("Save access grant", async () => { await sendJson(api+"/grants/"+g.id,"PUT",{permission_role:role.value,scope_mode:mode.value,status:status.value}); await load(); }));
        }
        details.append(row);
      }
      if (u.can_manage) {
        const form = node("div"); form.className = "network-form";
        const who = field(form,"Grant recipient VINYRD account ID","text");
        const role = field(form,"New permission profile","select",roles);
        const mode = field(form,`Scope for ${label(u)}`,"select",[["unit_only","This unit only"],...(u.can_manage_descendants ? [["descendants","This unit and descendants"]] : [])]);
        form.append(button("Create access grant",async () => { await sendJson(api+"/grants","POST",{user_id:who.value,organization_unit_id:u.id,permission_role:role.value,scope_mode:mode.value}); await load(); })); details.append(form);
      }
    }
    if (loadVersion !== generation) return;
    select.onchange = () => show().catch(e => message(e.message));
    await show();
  }
  window.VinyrdOrganizationAccess = {load};
})();
