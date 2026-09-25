(async () => {
  const mode = new URLSearchParams(location.search).get("mode") || "register";
  const form = document.querySelector("#accountForm");
  const status = document.querySelector("#accountStatus");
  const button = document.querySelector("#accountSubmit");
  const show = (selector, visible) => document.querySelectorAll(selector).forEach(node => {
    node.hidden = !visible;
    node.querySelectorAll("input").forEach(input => { input.disabled = !visible; });
  });
  if (mode === "profile" && !VinyrdClient.requireSession()) return;
  show("[data-profile-fields]", mode === "register" || mode === "profile");
  show("[data-email-field]", mode === "register" || mode === "forgot");
  show("[data-password-field]", mode === "register" || mode === "reset");
  show("[data-reset-token]", mode === "reset");
  if (mode !== "register") {
    const titles = {profile: "Your global profile", forgot: "Forgot password", reset: "Reset password"};
    document.querySelector("#accountTitle").textContent = titles[mode] || "Your account";
    document.querySelector("#accountIntro").textContent = mode === "profile"
      ? "Your profile belongs to you. Sharing contact details with a church is a separate choice."
      : "Use the recovery flow for your existing VINYRD account.";
    button.textContent = {profile: "Save profile", forgot: "Request password reset", reset: "Set new password"}[mode];
  }
  if (mode === "profile") {
    try {
      const profile = await VinyrdClient.apiRequest("/identity/me");
      Object.entries(profile).forEach(([key, value]) => { if (form.elements.namedItem(key)) form.elements.namedItem(key).value = value || ""; });
    } catch (error) { status.textContent = error.message; button.disabled = true; }
  }
  form.addEventListener("submit", async event => {
    event.preventDefault(); button.disabled = true; status.textContent = "Please wait…";
    const data = Object.fromEntries(new FormData(form));
    try {
      if (mode === "forgot") {
        const result = await VinyrdClient.publicRequest("/auth/password-reset/request", {method: "POST", body: JSON.stringify({email: data.email})});
        status.textContent = result.detail + " Contact your VINYRD support team if recovery delivery is not enabled.";
        if (result.demo_reset_token) {
          const link = document.createElement("a"); link.href = "./account.html?mode=reset"; link.textContent = "Continue local/test reset";
          sessionStorage.setItem("vinyrd_reset_token", result.demo_reset_token); status.append(" ", link);
        }
        return;
      }
      if (mode === "reset") {
        await VinyrdClient.publicRequest("/auth/password-reset/confirm", {method: "POST", body: JSON.stringify({token: data.token, new_password: data.password})});
        sessionStorage.removeItem("vinyrd_reset_token"); status.textContent = "Password updated. You can sign in now."; return;
      }
      if (mode === "register") {
        const result = await VinyrdClient.publicRequest("/auth/register", {method: "POST", body: JSON.stringify({
          first_name: data.first_name, last_name: data.last_name, email: data.email, password: data.password, phone: data.phone || null,
        })});
        VinyrdClient.setSession(result.access_token, result.user);
      }
      const profile = Object.fromEntries(["first_name", "last_name", "phone", "country", "region", "city", "avatar_url"].map(key => [key, data[key] || null]));
      await VinyrdClient.apiRequest("/identity/me", {method: "PUT", body: JSON.stringify(profile)});
      form.hidden = true; document.querySelector("#accountNext").hidden = false;
      status.textContent = mode === "profile" ? "Profile saved." : "Your account is ready. You can find a church or continue without one.";
    } catch (error) {
      status.textContent = error.message;
      if (mode === "register" && VinyrdClient.token()) {
        status.textContent += " Your account was created; finish your profile from Profile instead of registering again.";
        document.querySelector("#accountNext").hidden = false;
      }
    } finally { button.disabled = false; }
  });
  if (mode === "reset") form.elements.token.value = sessionStorage.getItem("vinyrd_reset_token") || "";
})();
