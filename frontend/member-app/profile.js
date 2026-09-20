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
      const data = await VinyrdClient.apiRequest("/member-portal/me");
      renderProfile(data.profile);
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        VinyrdClient.clearSession();
        window.location.replace("./login.html");
        return;
      }
      showToast("Could not load your profile.");
    }
  };

  qs("#editProfileButton").addEventListener("click", () => {
    showToast("Profile update requests are coming next.");
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
