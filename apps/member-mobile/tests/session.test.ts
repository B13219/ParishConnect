import { ApiClient, ApiError } from "../services/api";
import { SessionController, type TokenStorage } from "../services/session";
const user = {
  id: "u",
  name: "Ada Person",
  email: "ada@example.test",
  phone: null,
  roles: [],
};
const response = (body: unknown, status = 200) =>
  ({ ok: status < 400, status, json: async () => body }) as Response;
function fixture(saved: string | null = null) {
  let disk = saved;
  const storage: TokenStorage = {
    read: jest.fn(async () => disk),
    write: jest.fn(async (value) => {
      disk = value;
    }),
    remove: jest.fn(async () => {
      disk = null;
    }),
  };
  const transport = jest.fn<Promise<Response>, Parameters<typeof fetch>>();
  const api = new ApiClient("https://vinyrd.example/api/v1", transport);
  const session = new SessionController(api, storage);
  return { session, api, storage, transport, disk: () => disk };
}
test("restores a stored token only after validating the real auth/me endpoint", async () => {
  const f = fixture("saved");
  f.transport.mockResolvedValue(response({ user }));
  await f.session.restore();
  expect(f.session.snapshot().status).toBe("authenticated");
  expect(f.transport.mock.calls[0][0]).toBe(
    "https://vinyrd.example/api/v1/auth/me",
  );
  expect(f.transport.mock.calls[0][1]?.headers).toMatchObject({
    Authorization: "Bearer saved",
  });
});
test("a missing token starts anonymously without an API request", async () => {
  const f = fixture();
  await f.session.restore();
  expect(f.session.snapshot().status).toBe("anonymous");
  expect(f.transport).not.toHaveBeenCalled();
});
test("login supports an account with zero memberships and stores only the bearer token", async () => {
  const f = fixture();
  f.transport.mockResolvedValue(response({ access_token: "token", user }));
  await f.session.authenticate("login", {
    email: user.email,
    password: "password",
  });
  expect(f.session.snapshot().user).toEqual(user);
  expect(f.disk()).toBe("token");
  expect(f.transport).toHaveBeenCalledTimes(1);
  expect(f.transport.mock.calls[0][0]).toContain("/auth/login");
});
test("registration preserves password and sends only actual registration fields", async () => {
  const f = fixture();
  f.transport.mockResolvedValue(response({ access_token: "new", user }, 201));
  const payload = {
    first_name: "Ada",
    last_name: "Person",
    email: user.email,
    password: " spaced secret ",
  };
  await f.session.authenticate("register", payload);
  expect(JSON.parse(f.transport.mock.calls[0][1]?.body as string)).toEqual(
    payload,
  );
  expect(f.transport.mock.calls[0][0]).toContain("/auth/register");
  expect(f.session.snapshot().onboarding).toBe(true);
  f.session.completeOnboarding();
  expect(f.session.snapshot().onboarding).toBe(false);
});
test("invalid restored token is removed and the protected session is closed", async () => {
  const f = fixture("expired");
  f.transport.mockResolvedValue(response({ detail: "Expired" }, 401));
  await f.session.restore();
  await Promise.resolve();
  expect(f.session.snapshot().status).toBe("anonymous");
  expect(f.storage.remove).toHaveBeenCalled();
  expect(f.api.token()).toBeNull();
});
test("a network failure during restore keeps the token and offers retry instead of logging out", async () => {
  const f = fixture("saved");
  f.transport.mockRejectedValue(new Error("offline"));
  await f.session.restore();
  expect(f.session.snapshot().status).toBe("error");
  expect(f.disk()).toBe("saved");
  f.transport.mockResolvedValue(response({ user }));
  await f.session.restore();
  expect(f.session.snapshot().status).toBe("authenticated");
});
test("403 from a membership-only feature does not erase a valid zero-membership login", async () => {
  const f = fixture("valid");
  f.transport.mockResolvedValueOnce(response({ user }));
  await f.session.restore();
  f.transport.mockResolvedValue(
    response({ detail: "Membership required" }, 403),
  );
  await expect(f.api.request("/member-portal/me")).rejects.toMatchObject({
    status: 403,
  });
  expect(f.session.snapshot().status).toBe("authenticated");
  expect(f.disk()).toBe("valid");
});
test("failed secure storage does not expose an authenticated session and explains a created account", async () => {
  const f = fixture();
  f.transport.mockResolvedValue(response({ user, access_token: "new" }));
  jest.mocked(f.storage.write).mockRejectedValue(new Error("keystore"));
  await expect(
    f.session.authenticate("register", {
      first_name: "Ada",
      last_name: "Person",
      email: user.email,
      password: "longpassword",
    }),
  ).rejects.toThrow("account was created");
  expect(f.session.snapshot().status).not.toBe("authenticated");
  expect(f.api.token()).toBeNull();
});
test("logout clears local credentials even if the server is unreachable", async () => {
  const f = fixture("valid");
  f.transport.mockResolvedValueOnce(response({ user }));
  await f.session.restore();
  f.transport.mockRejectedValue(new Error("offline"));
  await f.session.logout();
  expect(f.disk()).toBeNull();
  expect(f.session.snapshot().status).toBe("anonymous");
});
test("late 401 from a previous session cannot clear a newer login", async () => {
  const f = fixture("old");
  f.transport.mockResolvedValueOnce(response({ user }));
  await f.session.restore();
  let finish!: (value: Response) => void;
  f.transport.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const old = f.api.request("/identity/me").catch(() => {});
  f.transport.mockResolvedValueOnce(response({ user, access_token: "new" }));
  await f.session.authenticate("login", {
    email: user.email,
    password: "secret",
  });
  finish(response({}, 401));
  await old;
  expect(f.api.token()).toBe("new");
  expect(f.session.snapshot().status).toBe("authenticated");
});
test("logout wins against in-flight login and serialized writes cannot restore its token", async () => {
  const f = fixture();
  let finish!: (value: Response) => void;
  f.transport.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const pending = f.session.authenticate("login", {
    email: user.email,
    password: "secret",
  });
  await f.session.logout();
  finish(response({ user, access_token: "late" }));
  await pending;
  expect(f.disk()).toBeNull();
  expect(f.api.token()).toBeNull();
});
test("Pydantic validation errors become readable messages", async () => {
  const f = fixture();
  f.transport.mockResolvedValue(
    response({ detail: [{ msg: "Invalid email" }] }, 422),
  );
  await expect(
    f.api.request("/auth/register", { public: true }),
  ).rejects.toEqual(new ApiError("Invalid email", 422));
});
test("release API configuration rejects HTTP before sending credentials", async () => {
  const transport = jest.fn();
  const api = new ApiClient("http://insecure.example/api/v1", transport);
  await expect(
    api.request("/auth/login", { public: true }),
  ).rejects.toMatchObject({ status: 0 });
  expect(transport).not.toHaveBeenCalled();
});
