import { ApiClient, ApiError } from "./api";
import type { Login, Registration, User } from "../types/api";
export interface TokenStorage {
  read(): Promise<string | null>;
  write(token: string): Promise<void>;
  remove(): Promise<void>;
}
export type Session = {
  status: "restoring" | "anonymous" | "authenticated" | "error";
  user: User | null;
  message: string | null;
  onboarding?: boolean;
};
export class SessionController {
  private value: Session = { status: "restoring", user: null, message: null };
  private accessToken: string | null = null;
  private revision = 0;
  private storageQueue: Promise<void> = Promise.resolve();
  private needsClear = false;
  private listeners = new Set<() => void>();
  constructor(
    public api: ApiClient,
    private storage: TokenStorage,
  ) {
    api.token = () => this.accessToken;
    api.onUnauthorized = (token) => {
      if (token === this.accessToken)
        void this.clear("Your session expired. Please sign in again.").catch(
          () => {},
        );
    };
  }
  snapshot = () => this.value;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private set(value: Session) {
    this.value = value;
    this.listeners.forEach((l) => l());
  }
  private persist(action: () => Promise<void>) {
    const next = this.storageQueue.catch(() => {}).then(action);
    this.storageQueue = next;
    return next;
  }
  async restore() {
    if (this.needsClear) return this.clear();
    const rev = ++this.revision;
    this.set({ status: "restoring", user: null, message: null });
    try {
      await this.storageQueue.catch(() => {});
      const token = await this.storage.read();
      if (rev !== this.revision) return;
      this.accessToken = token;
      if (!token) {
        this.set({ status: "anonymous", user: null, message: null });
        return;
      }
      const { user } = await this.api.request<{ user: User }>("/auth/me");
      if (rev === this.revision)
        this.set({ status: "authenticated", user, message: null });
    } catch (error) {
      if (rev === this.revision)
        this.set({
          status: "error",
          user: null,
          message:
            error instanceof Error
              ? error.message
              : "Unable to restore your session.",
        });
    }
  }
  async authenticate(
    mode: "login" | "register",
    payload: { email: string; password: string } | Registration,
  ) {
    const rev = ++this.revision;
    const response = await this.api.request<Login>(
      mode === "login" ? "/auth/login" : "/auth/register",
      { method: "POST", public: true, body: payload },
    );
    if (rev !== this.revision) return;
    try {
      await this.persist(() => this.storage.write(response.access_token));
    } catch {
      throw new ApiError(
        mode === "register"
          ? "Your account was created, but secure sign-in could not be saved. Sign in again; do not register twice."
          : "Could not save your session securely. Please try again.",
        0,
      );
    }
    if (rev !== this.revision) return;
    this.needsClear = false;
    this.accessToken = response.access_token;
    this.set({
      status: "authenticated",
      user: response.user,
      message: null,
      onboarding: mode === "register",
    });
  }
  async clear(message: string | null = null) {
    const rev = ++this.revision;
    this.accessToken = null;
    this.set({ status: "anonymous", user: null, message });
    try {
      await this.persist(() => this.storage.remove());
      this.needsClear = false;
    } catch {
      this.needsClear = true;
      if (rev === this.revision)
        this.set({
          status: "error",
          user: null,
          message:
            "Secure session removal failed. Retry before leaving this device.",
        });
    }
  }
  completeOnboarding() {
    this.set({ ...this.value, onboarding: false });
  }
  async logout() {
    const notify = this.accessToken
      ? this.api.request("/auth/logout", { method: "POST" }).catch(() => {})
      : Promise.resolve();
    await this.clear();
    void notify;
  }
}
