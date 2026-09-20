if (VinyrdClient.requireSession()) {
  const qs = (selector) => document.querySelector(selector);
  let toastTimer;

  const showToast = (message) => {
    const toast = qs("#statusToast");
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("show"), 2300);
  };

  const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);

  const formatDate = (value) =>
    new Intl.DateTimeFormat(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(new Date(value));

  const lessonCard = (lesson) => {
    const context = [
      lesson.event_name,
      lesson.speaker_name ? "Speaker: " + lesson.speaker_name : null,
      lesson.scripture_reference,
    ].filter(Boolean).join(" • ");

    return '<article class="sermon-lesson-card">' +
      '<div class="sermon-lesson-topline">' +
        '<div><strong>' + escapeHtml(lesson.sermon_title) + '</strong>' +
          '<span>' + escapeHtml(formatDate(lesson.created_at)) + '</span></div>' +
        '<span class="sermon-private-badge">Private</span>' +
      '</div>' +
      (context ? '<small>' + escapeHtml(context) + '</small>' : '') +
      '<p>' + escapeHtml(lesson.key_lesson) + '</p>' +
      (lesson.action_point
        ? '<div class="sermon-action-point"><strong>Action</strong><span>' +
          escapeHtml(lesson.action_point) + '</span></div>'
        : '') +
    '</article>';
  };

  const renderLessons = (lessons) => {
    qs("#sermonLessonCount").textContent = String(lessons.length);
    qs("#sermonLessonsList").innerHTML = lessons.length
      ? lessons.map(lessonCard).join("")
      : '<div class="sermon-empty">You have not saved a sermon lesson yet.</div>';
  };

  const loadEvents = async () => {
    try {
      const events = await VinyrdClient.apiRequest("/member-portal/events");
      const select = qs("#lessonEvent");
      const sorted = [...events].sort(
        (a, b) => new Date(b.starts_at).getTime() - new Date(a.starts_at).getTime()
      );

      sorted.forEach((event) => {
        const option = document.createElement("option");
        option.value = event.id;
        option.textContent = event.name + " - " + formatDate(event.starts_at);
        select.appendChild(option);
      });
    } catch {
    }
  };

  const loadLessons = async () => {
    try {
      const lessons = await VinyrdClient.apiRequest("/member-portal/sermon-lessons");
      renderLessons(lessons);
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        VinyrdClient.clearSession();
        window.location.replace("./login.html");
        return;
      }
      showToast("Could not load your sermon lessons.");
    }
  };

  qs("#sermonLessonForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = qs("#submitSermonLesson");
    const data = new FormData(form);

    submit.disabled = true;
    submit.textContent = "Saving...";

    try {
      await VinyrdClient.apiRequest("/member-portal/sermon-lessons", {
        method: "POST",
        body: JSON.stringify({
          event_id: String(data.get("event_id") || "") || null,
          sermon_title: String(data.get("sermon_title") || "").trim(),
          speaker_name: String(data.get("speaker_name") || "").trim() || null,
          scripture_reference: String(data.get("scripture_reference") || "").trim() || null,
          key_lesson: String(data.get("key_lesson") || "").trim(),
          action_point: String(data.get("action_point") || "").trim() || null,
        }),
      });

      form.reset();
      showToast("Sermon lesson saved.");
      await loadLessons();
    } catch (error) {
      showToast(error.message || "Could not save your sermon lesson.");
    } finally {
      submit.disabled = false;
      submit.textContent = "Save lesson";
    }
  });

  loadEvents();
  loadLessons();
}
