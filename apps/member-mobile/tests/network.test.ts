import { ApiClient } from "../services/api";
import { createServices } from "../services/endpoints";
import { NetworkController } from "../services/networkState";
import type { Network } from "../types/api";
const a = {
  id: "ma",
  church_id: "a",
  church_name: "Church A",
  status: "active" as const,
  is_primary: true,
  legacy_member_id: "legacy-a",
};
const b = {
  ...a,
  id: "mb",
  church_id: "b",
  church_name: "Church B",
  is_primary: false,
  legacy_member_id: "legacy-b",
};
function fixture(
  data: Network = { memberships: [a, b], requests: [], follows: [] },
) {
  const transport = jest.fn(
    async (_url: Parameters<typeof fetch>[0], _options?: RequestInit) =>
      ({ ok: true, status: 200, json: async () => data }) as Response,
  );
  const api = new ApiClient("https://vinyrd.example/api/v1", transport);
  api.token = () => "token";
  const services = createServices(api);
  return { services, transport, controller: new NetworkController(services) };
}
test("empty memberships are a valid network state", async () => {
  const f = fixture({ memberships: [], requests: [], follows: ["a"] });
  await f.controller.refresh();
  expect(f.controller.snapshot()).toMatchObject({
    viewedChurchId: null,
    error: null,
    loading: false,
  });
  expect(f.controller.snapshot().data?.follows).toEqual(["a"]);
});
test("approved memberships initialize viewed context from server Home Church", async () => {
  const f = fixture();
  await f.controller.refresh();
  expect(f.controller.snapshot().viewedChurchId).toBe("a");
  expect(f.transport.mock.calls[0][0]).toContain("/network/me/initialize-home");
  expect(f.transport.mock.calls[1][0]).toContain("/network/me");
});
test("switching viewed church does not mutate Home Church", async () => {
  const f = fixture();
  await f.controller.refresh();
  f.transport.mockClear();
  f.controller.selectChurch("b");
  expect(f.controller.snapshot().viewedChurchId).toBe("b");
  expect(f.controller.snapshot().data?.memberships[0].is_primary).toBe(true);
  expect(f.transport).not.toHaveBeenCalled();
  expect(() => f.controller.selectChurch("outsider")).toThrow(
    "active membership",
  );
});
test("Home Church selection calls owner API and preserves current view", async () => {
  const f = fixture();
  await f.controller.refresh();
  f.controller.selectChurch("b");
  await f.controller.setHome("ma");
  expect(
    f.transport.mock.calls.some(
      ([url, options]) =>
        String(url).endsWith("/identity/memberships/ma/primary") &&
        options?.method === "PUT",
    ),
  ).toBe(true);
  expect(f.controller.snapshot().viewedChurchId).toBe("b");
});
test("a revoked viewed membership is dropped during refresh", async () => {
  const state: Network = { memberships: [a, b], requests: [], follows: [] };
  const f = fixture(state);
  await f.controller.refresh();
  f.controller.selectChurch("b");
  state.memberships = [a, { ...b, status: "suspended" }];
  await f.controller.refresh();
  expect(f.controller.snapshot().viewedChurchId).toBe("a");
});
test("discovery uses the public network API with structured geography", async () => {
  const f = fixture();
  await f.services.discover(
    {
      q: "Chapel",
      country: "TZ",
      region: "Arusha",
      city: "Arusha",
      denomination: "Lutheran",
      view: "tanzania",
    },
    24,
  );
  const [url, options] = f.transport.mock.calls[0];
  const parsed = new URL(String(url));
  expect(parsed.pathname).toBe("/api/v1/network/churches");
  expect(parsed.searchParams.get("country")).toBe("TZ");
  expect(parsed.searchParams.get("offset")).toBe("24");
  expect(options?.headers).not.toHaveProperty("Authorization");
});
test("follow and unfollow never call membership endpoints", async () => {
  const f = fixture();
  await f.services.follow("a", true);
  await f.services.follow("a", false);
  expect(
    f.transport.mock.calls.map(([url, options]) => [url, options?.method]),
  ).toEqual([
    ["https://vinyrd.example/api/v1/identity/churches/a/follow", "PUT"],
    ["https://vinyrd.example/api/v1/identity/churches/a/follow", "DELETE"],
  ]);
});
test("membership requests preserve explicit contact consent and do not send approval fields", async () => {
  const f = fixture();
  await f.services.join("a", "Hello", false);
  expect(f.transport.mock.calls[0][0]).toContain(
    "/identity/churches/a/requests",
  );
  expect(JSON.parse(f.transport.mock.calls[0][1]?.body as string)).toEqual({
    message: "Hello",
    share_contact: false,
  });
});
test("portal context is an explicit request header, never part of global identity mutations", async () => {
  const f = fixture();
  await f.services.home("b");
  await f.services.setHome("ma");
  expect(f.transport.mock.calls[0][1]?.headers).toMatchObject({
    "X-Church-ID": "b",
    Authorization: "Bearer token",
  });
  expect(f.transport.mock.calls[1][1]?.headers).not.toHaveProperty(
    "X-Church-ID",
  );
});
test("pending, more-info and rejected requests stay readable without a membership", async () => {
  const data: Network = {
    memberships: [],
    follows: ["a"],
    requests: ["pending", "more_info_required", "rejected"].map(
      (status, i) => ({
        id: String(i),
        church_id: "a",
        status: status as Network["requests"][number]["status"],
        created_at: "2026-09-25",
        message: null,
        rejection_reason: "Contact church",
      }),
    ),
  };
  const f = fixture(data);
  await f.controller.refresh();
  expect(f.controller.snapshot().data?.requests).toEqual(data.requests);
  expect(f.controller.snapshot().viewedChurchId).toBeNull();
});
