export type User = {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  roles: string[];
};
export type Login = { access_token: string; user: User };
export type Registration = {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  phone?: string | null;
};
export type ProfileInput = {
  first_name: string;
  last_name: string;
  phone: string | null;
  avatar_url: string | null;
  country: string | null;
  region: string | null;
  city: string | null;
};
export type Profile = ProfileInput & { user_id: string; email: string };
export type Membership = {
  id: string;
  church_id: string;
  church_name: string;
  status: "pending" | "active" | "inactive" | "former" | "suspended";
  is_primary: boolean;
  legacy_member_id: string | null;
};
export type MembershipRequest = {
  id: string;
  church_id: string;
  status:
    | "pending"
    | "approved"
    | "rejected"
    | "more_info_required"
    | "cancelled";
  message: string | null;
  created_at: string;
  rejection_reason: string | null;
};
export type Network = {
  memberships: Membership[];
  requests: MembershipRequest[];
  follows: string[];
};
export type PublicItem = {
  title: string;
  body: string;
  starts_at: string | null;
  location: string | null;
};
export type Church = {
  church_id: string;
  name: string;
  country: string;
  region: string | null;
  city: string | null;
  denomination: string | null;
  location: string | null;
  logo_url: string | null;
  about: string | null;
  service_times: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  website: string | null;
  public_events: PublicItem[];
  public_announcements: PublicItem[];
  public_ministries: PublicItem[];
};
export type DenominationLevel = {
  key: string;
  label: string;
  optional: boolean;
};
export type DenominationOption = {
  value: string;
  label: string;
  governance_model: string;
  levels: DenominationLevel[];
};
export type DenominationCatalog = {
  items: DenominationOption[];
  custom_allowed: boolean;
};
export type DiscoveryFilters = {
  q?: string;
  country?: string;
  region?: string;
  city?: string;
  denomination?: string;
  view?: "all" | "local" | "new" | "tanzania";
};
export type DiscoveryPage = {
  items: Church[];
  has_more: boolean;
  offset: number;
  limit: number;
};
export type Event = {
  id: string;
  name: string;
  starts_at: string;
  location: string | null;
  checked_in: boolean;
};
export type Message = {
  id: string;
  subject: string | null;
  body: string;
  channel: string;
  sent_at: string;
};
export type Contribution = {
  id: string;
  type: string;
  amount: string;
  currency: string;
  received_at: string;
  payment_method: string;
};
export type PortalHome = {
  profile: { name: string; branch_name: string };
  giving: { total_amount: string; currency: string; latest: Contribution[] };
};
export type Group = {
  id: string;
  name: string;
  role: string;
  leader_name: string | null;
  meeting_day?: string | null;
  area?: string | null;
};
export type Groups = {
  community_label: string;
  communities: Group[];
  ministries: Group[];
};
export type Prayer = {
  id: string;
  body: string;
  status: string;
  category: string;
  created_at: string;
};
export type PrayerInput = {
  body: string;
  category:
    | "general"
    | "family"
    | "health"
    | "work"
    | "guidance"
    | "thanksgiving";
  visibility: "pastoral_team" | "shareable";
  allow_contact: boolean;
};
export type Sermon = {
  id: string;
  title: string | null;
  speaker: string | null;
  scripture_reference: string | null;
  summary: string | null;
  event_name: string;
  starts_at: string;
};
export type Lesson = {
  id: string;
  sermon_title: string;
  scripture_reference: string | null;
  key_lesson: string;
  action_point: string | null;
};
