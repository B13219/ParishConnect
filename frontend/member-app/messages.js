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

  const formatDate = (value) => {
    if (!value) return "Sent";
    return new Intl.DateTimeFormat(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(value));
  };

  const messageCard = (message, index) => {
    const subject = message.subject || "Church message";
    const body = message.body || "";
    const preview = body.length > 120 ? body.slice(0, 120) + "..." : body;
    const messageId = "member-message-" + index;

    return '<article class="member-message-card">' +
      '<button class="member-message-summary" type="button" data-message-toggle="' +
        escapeHtml(messageId) + '">' +
        '<div class="member-message-icon"><img src="./assets/icon-messages.svg" alt=""></div>' +
        '<div class="member-message-copy">' +
          '<div class="member-message-topline"><strong>' + escapeHtml(subject) + '</strong>' +
            '<span>' + escapeHtml(formatDate(message.sent_at)) + '</span></div>' +
          '<small>' + escapeHtml(labelize(message.channel || "message")) + '</small>' +
          '<p>' + escapeHtml(preview) + '</p>' +
        '</div>' +
      '</button>' +
      '<div class="member-message-body" id="' + escapeHtml(messageId) + '" hidden>' +
        '<p>' + escapeHtml(body) + '</p>' +
      '</div>' +
    '</article>';
  };

  const renderMessages = (messages) => {
    qs("#messageCount").textContent = String(messages.length);
    qs("#messagesList").innerHTML = messages.length
      ? messages.map(messageCard).join("")
      : '<div class="messages-empty">No messages have been sent to your member account yet.</div>';

    document.querySelectorAll("[data-message-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const panel = document.getElementById(button.dataset.messageToggle);
        const opening = panel.hidden;
        panel.hidden = !opening;
        button.classList.toggle("open", opening);
      });
    });
  };

  const loadMessages = async () => {
    try {
      const messages = await VinyrdClient.apiRequest("/member-portal/messages");
      renderMessages(messages);
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
      showToast("Could not load your messages.");
    }
  };

  loadMessages();
}
