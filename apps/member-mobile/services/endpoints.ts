import { ApiClient } from "./api";
import type {
  Church,
  DiscoveryFilters,
  DiscoveryPage,
  Profile,
  ProfileInput,
  Network,
  MembershipRequest,
  Membership,
  PortalHome,
  Event,
  Groups,
  Message,
  Prayer,
  PrayerInput,
  Sermon,
  Lesson,
} from "../types/api";
export const createServices = (api: ApiClient) => ({
  profile: () => api.request<Profile>("/identity/me"),
  updateProfile: (body: ProfileInput) =>
    api.request<Profile>("/identity/me", { method: "PUT", body }),
  network: () => api.request<Network>("/network/me"),
  initializeHome: () =>
    api.request<{ home_church_id: string | null }>(
      "/network/me/initialize-home",
      { method: "POST" },
    ),
  setHome: (id: string) =>
    api.request<Membership>(
      `/identity/memberships/${encodeURIComponent(id)}/primary`,
      { method: "PUT" },
    ),
  discover: (filters: DiscoveryFilters, offset = 0) => {
    const params = new URLSearchParams({
      ...filters,
      offset: String(offset),
      limit: "24",
    });
    return api.request<DiscoveryPage>("/network/churches?" + params, {
      public: true,
    });
  },
  church: (id: string) =>
    api.request<Church>(`/network/churches/${encodeURIComponent(id)}`, {
      public: true,
    }),
  follow: (id: string, following: boolean) =>
    api.request(`/identity/churches/${encodeURIComponent(id)}/follow`, {
      method: following ? "PUT" : "DELETE",
    }),
  join: (id: string, message: string, share_contact: boolean) =>
    api.request<MembershipRequest>(
      `/identity/churches/${encodeURIComponent(id)}/requests`,
      {
        method: "POST",
        body: { message: message.trim() || null, share_contact },
      },
    ),
  cancel: (id: string) =>
    api.request<MembershipRequest>(
      `/identity/requests/${encodeURIComponent(id)}/cancel`,
      { method: "POST" },
    ),
  home: (churchId: string) =>
    api.request<PortalHome>("/member-portal/me", { churchId }),
  events: (churchId: string) =>
    api.request<Event[]>("/member-portal/events", { churchId }),
  groups: (churchId: string) =>
    api.request<Groups>("/member-portal/groups", { churchId }),
  messages: (churchId: string) =>
    api.request<Message[]>("/member-portal/messages", { churchId }),
  prayers: (churchId: string) =>
    api.request<Prayer[]>("/member-portal/prayers", { churchId }),
  sendPrayer: (churchId: string, body: PrayerInput) =>
    api.request<Prayer>("/member-portal/prayers", {
      method: "POST",
      churchId,
      body,
    }),
  sermons: (churchId: string) =>
    api.request<Sermon[]>("/member-portal/sermons", { churchId }),
  lessons: (churchId: string) =>
    api.request<Lesson[]>("/member-portal/sermon-lessons", { churchId }),
});
export type Services = ReturnType<typeof createServices>;
