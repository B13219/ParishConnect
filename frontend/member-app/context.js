(() => {
  if (!VinyrdClient.token()) return;
  VinyrdClient.contextReady = (async () => {
    await VinyrdClient.apiRequest("/network/me/initialize-home", {
      method: "POST",
    });
    const data = await VinyrdClient.apiRequest("/network/me");
    const active = data.memberships.filter((m) => m.status === "active");
    const selected =
      active.find((m) => m.church_id === VinyrdClient.viewedChurch()) ||
      active.find((m) => m.is_primary) ||
      active[0];
    VinyrdClient.setViewedChurch(selected?.church_id);
    const panel = document.createElement("section");
    panel.className = "network-context";
    const label = document.createElement("label");
    label.textContent = "Currently viewing";
    if (active.length) {
      const select = document.createElement("select");
      select.className = "network-select";
      active.forEach((m) => {
        const option = document.createElement("option");
        option.value = m.church_id;
        option.textContent =
          m.church_name + (m.is_primary ? " · Home Church" : "");
        select.append(option);
      });
      select.value = selected.church_id;
      select.addEventListener("change", () => {
        VinyrdClient.setViewedChurch(select.value);
        location.reload();
      });
      label.append(select);
      panel.append(label);
    }
    const note = document.createElement("small");
    note.textContent = active.length
      ? "Viewing a church does not change Home Church or your memberships. "
      : "Your global VINYRD account is ready. ";
    const link = document.createElement("a");
    link.href = "./my-church.html";
    link.textContent = "Manage churches";
    note.append(link);
    panel.append(note);
    document.querySelector("main > header")?.after(panel);
  })();
  // Portal calls await this promise, so failed context validation never sends a stale context.
  VinyrdClient.contextReady.catch((error) => {
    const panel = document.createElement("p");
    panel.className = "network-context";
    panel.textContent = error.message;
    document.querySelector("main > header")?.after(panel);
  });
})();
