const form = document.querySelector("#memberLoginForm");
const errorBox = document.querySelector("#loginError");
const button = document.querySelector("#loginButton");

const showError = (message) => {
  errorBox.textContent = message;
};

const validateExistingSession = async () => {
  if (!VinyrdClient.token()) return;
  try {
    await VinyrdClient.apiRequest("/auth/me");
    window.location.replace("./home.html");
  } catch {
    VinyrdClient.clearSession();
  }
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("");
  button.disabled = true;
  button.textContent = "Signing in...";

  const data = new FormData(form);
  try {
    const login = await VinyrdClient.publicRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: String(data.get("email") || "").trim(),
        password: String(data.get("password") || ""),
      }),
    });

    VinyrdClient.setSession(login.access_token, login.user);

    try {
      await VinyrdClient.apiRequest("/auth/me");
    } catch (error) {
      VinyrdClient.clearSession();
      throw error;
    }

    window.location.replace("./home.html");
  } catch (error) {
    showError(error.message || "Sign in failed.");
    button.disabled = false;
    button.textContent = "Sign in";
  }
});

validateExistingSession();


const passwordInput = document.querySelector("#memberPassword");
const togglePassword = document.querySelector("#togglePassword");

togglePassword?.addEventListener("click", () => {
  const show = passwordInput.type === "password";
  passwordInput.type = show ? "text" : "password";
  togglePassword.textContent = show ? "Hide" : "Show";
  togglePassword.setAttribute("aria-label", show ? "Hide password" : "Show password");
});
