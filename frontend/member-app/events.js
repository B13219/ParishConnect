if (VinyrdClient.requireSession()) {
  const qs = (selector) => document.querySelector(selector);
  let toastTimer;

  const showToast = (message) => {
    const toast = qs("#statusToast");
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2400);
  };

  const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);

  const labelize = (value) =>
    String(value || "")
      .replaceAll("_", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());

  const dateParts = (value) => {
    const date = new Date(value);
    return {
      day: String(date.getDate()).padStart(2, "0"),
      month: date.toLocaleString(undefined, {month: "short"}).toUpperCase(),
    };
  };

  const formatDateTime = (value) =>
    new Intl.DateTimeFormat(undefined, {
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(value));

  const upcomingEvents = (events) => {
    const cutoff = Date.now() - 6 * 60 * 60 * 1000;
    return events.filter((event) => new Date(event.starts_at).getTime() >= cutoff);
  };

  const renderHero = (event) => {
    if (!event) {
      qs("#nextEventName").textContent = "No upcoming events";
      qs("#nextEventWhen").textContent = "Check back soon";
      qs("#nextEventLocation").textContent = "Vinyrd";
      return;
    }
    const parts = dateParts(event.starts_at);
    qs("#nextEventDay").textContent = parts.day;
    qs("#nextEventMonth").textContent = parts.month;
    qs("#nextEventName").textContent = event.name;
    qs("#nextEventWhen").textContent = formatDateTime(event.starts_at);
    qs("#nextEventLocation").textContent = event.location || "Location to be confirmed";
  };

  const actionForEvent = (event) => {
    if (event.checked_in) {
      return '<span class="event-attendance-badge checked">Checked in</span>';
    }
    if (event.attendance_window_open && event.geofence_available) {
      return '<button class="event-checkin-button" type="button" data-check-in="' +
        escapeHtml(event.id) + '">Check in here</button>';
    }
    if (event.attendance_status === "open") {
      return '<span class="event-attendance-badge">Attendance open</span>';
    }
    return '<span class="event-attendance-badge muted">Scheduled</span>';
  };

  const renderEvents = (events) => {
    const upcoming = upcomingEvents(events);
    renderHero(upcoming[0] || null);
    qs("#eventCount").textContent = String(upcoming.length);

    qs("#eventsList").innerHTML = upcoming.length
      ? upcoming.map((event) => {
          const parts = dateParts(event.starts_at);
          return '<article class="events-row">' +
            '<div class="events-row-date"><strong>' + escapeHtml(parts.day) + '</strong><span>' + escapeHtml(parts.month) + '</span></div>' +
            '<div class="events-row-copy"><strong>' + escapeHtml(event.name) + '</strong>' +
              '<span>' + escapeHtml(formatDateTime(event.starts_at)) + '</span>' +
              '<span>' + escapeHtml(event.location || "Location to be confirmed") + '</span>' +
              '<small>' + escapeHtml(labelize(event.type)) + '</small></div>' +
            '<div class="events-row-action">' + actionForEvent(event) + '</div>' +
          '</article>';
        }).join("")
      : '<div class="events-empty">No upcoming events found.</div>';

    document.querySelectorAll("[data-check-in]").forEach((button) => {
      button.addEventListener("click", () => checkInWithLocation(button.dataset.checkIn, button));
    });
  };

  const position = () =>
    new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Location services are not supported on this device."));
        return;
      }
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 0,
      });
    });

  const locationError = (error) => {
    if (error && error.body && error.body.detail && typeof error.body.detail === "object") {
      const detail = error.body.detail;
      if (detail.reason === "outside_geofence") {
        return "You are " + detail.distance_meters + " m from the church. Check-in radius is " +
          detail.allowed_radius_meters + " m.";
      }
    }
    if (error.code === 1) return "Location permission was denied.";
    if (error.code === 2) return "Your location could not be determined.";
    if (error.code === 3) return "Location request timed out.";
    return error.message || "Location check-in failed.";
  };

  const checkInWithLocation = async (eventId, button) => {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Finding you...";
    qs("#eventCheckinStatus").textContent = "";

    try {
      const result = await position();
      button.textContent = "Confirming...";
      const coords = result.coords;

      const attendance = await VinyrdClient.apiRequest(
        "/member-portal/events/" + eventId + "/check-in/location",
        {
          method: "POST",
          body: JSON.stringify({
            latitude: coords.latitude,
            longitude: coords.longitude,
            accuracy_meters: coords.accuracy,
          }),
        }
      );

      qs("#eventCheckinStatus").textContent =
        "Attendance confirmed. You were " + attendance.distance_meters + " m from the church.";
      showToast("Attendance confirmed.");
      await loadEvents();
    } catch (error) {
      button.disabled = false;
      button.textContent = original;
      qs("#eventCheckinStatus").textContent = locationError(error);
    }
  };

  const loadEvents = async () => {
    try {
      const events = await VinyrdClient.apiRequest("/member-portal/events");
      renderEvents(events);
    } catch (error) {
      if (error.status === 403) {
        window.location.replace("./home.html");
        return;
      }
      if (error.status === 401) {
        VinyrdClient.clearSession();
        window.location.replace("./login.html");
        return;
      }
      showToast("Could not load church events.");
    }
  };

  document.querySelectorAll("[data-route]").forEach((control) => {
    control.addEventListener("click", (event) => {
      event.preventDefault();
      const route = control.dataset.route;
      showToast(route.charAt(0).toUpperCase() + route.slice(1) + " is the next Vinyrd screen.");
    });
  });

  loadEvents();
}
