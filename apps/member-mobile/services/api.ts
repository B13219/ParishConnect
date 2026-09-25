export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
type Options = {
  method?: string;
  body?: unknown;
  public?: boolean;
  churchId?: string;
};
export class ApiClient {
  token: () => string | null = () => null;
  onUnauthorized: (usedToken: string) => void = () => {};
  constructor(
    private base: string,
    private transport: typeof fetch = fetch,
    private allowHttp = false,
  ) {}
  async request<T>(path: string, options: Options = {}): Promise<T> {
    const base = this.base.trim().replace(/\/+$/, "");
    if (
      !/^https:\/\//.test(base) &&
      !(this.allowHttp && /^http:\/\//.test(base))
    ) {
      throw new ApiError(
        "Configure EXPO_PUBLIC_VINYRD_API_BASE with a reachable HTTPS API URL including /api/v1.",
        0,
      );
    }
    const token = options.public ? null : this.token();
    if (!options.public && !token) throw new ApiError("Please sign in.", 401);
    const headers: Record<string, string> = { Accept: "application/json" };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (options.body !== undefined)
      headers["Content-Type"] = "application/json";
    if (path.startsWith("/member-portal/") && options.churchId)
      headers["X-Church-ID"] = options.churchId;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await this.transport(base + path, {
        method: options.method || "GET",
        headers,
        body:
          options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: controller.signal,
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        if (response.status === 401 && token) this.onUnauthorized(token);
        const detail = body?.detail;
        const message =
          typeof detail === "string"
            ? detail
            : Array.isArray(detail)
              ? detail
                  .map((item: { msg?: string }) => item.msg || "Invalid value")
                  .join("; ")
              : `Request failed (${response.status}).`;
        throw new ApiError(message, response.status);
      }
      return body as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(
        "Could not reach VINYRD. Check your connection and try again.",
        0,
      );
    } finally {
      clearTimeout(timer);
    }
  }
}
