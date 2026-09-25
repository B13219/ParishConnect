(() => {
  const API_BASE =
    window.VINYRD_API_BASE ||
    (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost"
      ? "http://127.0.0.1:8003/api/v1"
      : "/api/v1");

  const TOKEN_KEY = "vinyrd_member_access_token";
  const USER_KEY = "vinyrd_member_user";

  const token = () => sessionStorage.getItem(TOKEN_KEY);

  const setSession = (accessToken, user) => {
    sessionStorage.setItem(TOKEN_KEY, accessToken);
    sessionStorage.setItem(USER_KEY, JSON.stringify(user || {}));
  };

  const clearSession = () => {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
  };

  const parseResponse = async (response) => {
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = Array.isArray(body.detail) ? body.detail.map(item => item.msg).join("; ") : body.detail;
      const error = new Error(typeof detail === "string" ? detail : "Request failed with " + response.status);
      error.status = response.status;
      error.body = body;
      throw error;
    }
    return body;
  };

  const publicRequest = async (path, options = {}) => {
    const headers = new Headers(options.headers || {});
    if (options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const response = await fetch(API_BASE + path, {...options, headers});
    return parseResponse(response);
  };

  const apiRequest = async (path, options = {}) => {
    const accessToken = token();
    if (!accessToken) {
      const error = new Error("Login required.");
      error.status = 401;
      throw error;
    }

    const headers = new Headers(options.headers || {});
    headers.set("Authorization", "Bearer " + accessToken);
    if (options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(API_BASE + path, {...options, headers});
    try {
      return await parseResponse(response);
    } catch (error) {
      if (error.status === 401) clearSession();
      throw error;
    }
  };

  const requireSession = () => {
    if (token()) return true;
    window.location.replace("./login.html");
    return false;
  };

  window.VinyrdClient = {
    API_BASE,
    token,
    setSession,
    clearSession,
    publicRequest,
    apiRequest,
    requireSession,
  };
})();
