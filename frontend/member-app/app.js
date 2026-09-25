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

  const firstName = (profile) =>
    (profile && (profile.first_name || profile.name) || "Member").trim().split(/\s+/)[0];

  const greetingForHour = (hour) => {
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  };

  const formatEventWhen = (value) => {
    if (!value) return "Date to be confirmed";
    return new Intl.DateTimeFormat(undefined, {
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(value));
  };

  const nextEvent = (events) => {
    events = events || [];
    if (!events.length) return null;
    const now = Date.now();
    return events.find((event) => new Date(event.starts_at).getTime() >= now) || events[0];
  };

  const renderEvent = (event) => {
    if (!event) {
      qs("#eventTitle").textContent = "No upcoming events";
      qs("#eventWhen").textContent = "Check back soon";
      qs("#eventLocation").textContent = "Vinyrd";
      qs("#eventDay").textContent = "--";
      qs("#eventMonth").textContent = "---";
      return;
    }
    const date = event.starts_at ? new Date(event.starts_at) : null;
    qs("#eventTitle").textContent = event.name || "Church Event";
    qs("#eventWhen").textContent = formatEventWhen(event.starts_at);
    qs("#eventLocation").textContent = event.location || "Location to be confirmed";
    qs("#eventDay").textContent = date ? String(date.getDate()).padStart(2, "0") : "--";
    qs("#eventMonth").textContent = date ? date.toLocaleString(undefined, {month: "short"}).toUpperCase() : "---";
  };

  const loadHome = async () => {
    const indicator = qs("#connectionDot");
    try {
      const data = await VinyrdClient.apiRequest("/member-portal/me");
      qs("#memberGreeting").textContent =
        greetingForHour(new Date().getHours()) + ", " + firstName(data.profile);
      renderEvent(nextEvent(data.events));
      indicator.classList.add("ok");
    } catch (error) {
      if (error.status === 403) {
        try {
          const profile = await VinyrdClient.apiRequest("/identity/me");
          qs("#memberGreeting").textContent =
            greetingForHour(new Date().getHours()) + ", " + firstName(profile);
          renderEvent(null);
          qs("#eventTitle").textContent = "Welcome to VINYRD";
          qs("#eventWhen").textContent = "Your account is ready. Church membership is separate.";
          indicator.classList.add("ok");
        } catch {
          showToast("Could not load your account.");
        }
        return;
      }
      if (error.status === 401) {
        VinyrdClient.clearSession();
        window.location.replace("./login.html");
        return;
      }
      indicator.classList.add("error");
      renderEvent(null);
      showToast("Could not reach the member API.");
    }
  };

  document.querySelectorAll("[data-route]").forEach((control) => {
    control.addEventListener("click", (event) => {
      const route = control.dataset.route;
      if (route === "profile") return;
      event.preventDefault();
      showToast(route.charAt(0).toUpperCase() + route.slice(1) + " is the next Vinyrd screen.");
    });
  });

  loadHome();
}
