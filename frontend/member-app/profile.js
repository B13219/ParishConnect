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

  const initials = (profile) => {
    const parts = [profile && profile.first_name, profile && profile.last_name].filter(Boolean);
    return parts.map((part) => part.trim().charAt(0)).join("").slice(0, 2).toUpperCase() || "M";
  };

  const renderProfile = (profile) => {
    qs("#profileInitials").textContent = initials(profile);
    qs("#profileName").textContent = profile.name || "Member";
    qs("#profileMeta").textContent = "Member - " + (profile.branch_name || "Church branch");
    qs("#profilePhone").textContent = profile.phone || "Not provided";
    qs("#profileEmail").textContent = profile.email || "Not provided";
    qs("#profileBranch").textContent = profile.branch_name || "Church branch";
    qs("#profileMemberCode").textContent = profile.member_code || profile.id;
  };

  const loadProfile = async () => {
    try {
      const [data, globalProfile] = await Promise.all([VinyrdClient.apiRequest("/member-portal/me"), VinyrdClient.apiRequest("/identity/me")]);
      renderProfile({...data.profile, ...globalProfile, name: globalProfile.first_name + " " + globalProfile.last_name});
    } catch (error) {
      if (error.status === 403) {
        const profile = await VinyrdClient.apiRequest("/identity/me");
        renderProfile({...profile, id: profile.user_id,
          name: profile.first_name + " " + profile.last_name,
          branch_name: "No active home church"});
        qs("#profileMeta").textContent = "VINYRD account";
        return;
      }
      if (error.status === 401) {
        VinyrdClient.clearSession();
        window.location.replace("./login.html");
        return;
      }
      showToast("Could not load your profile.");
    }
  };

  qs("#editProfileButton").addEventListener("click", () => {
    window.location.href = "./account.html?mode=profile";
  });

  qs("#signOutButton").addEventListener("click", async () => {
    try {
      await VinyrdClient.apiRequest("/auth/logout", {method: "POST"});
    } catch {
    }
    VinyrdClient.clearSession();
    window.location.replace("./login.html");
  });

  document.querySelectorAll("[data-route]").forEach((control) => {
    control.addEventListener("click", (event) => {
      event.preventDefault();
      const route = control.dataset.route;
      showToast(route.charAt(0).toUpperCase() + route.slice(1) + " is the next Vinyrd screen.");
    });
  });

  loadProfile();
}
