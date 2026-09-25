import type { Network } from "../types/api";
import type { Services } from "./endpoints";
export type NetworkState = {
  data: Network | null;
  viewedChurchId: string | null;
  loading: boolean;
  error: string | null;
};
export class NetworkController {
  private value: NetworkState = {
    data: null,
    viewedChurchId: null,
    loading: true,
    error: null,
  };
  private revision = 0;
  private listeners = new Set<() => void>();
  constructor(private services: Services) {}
  snapshot = () => this.value;
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  private set(value: NetworkState) {
    this.value = value;
    this.listeners.forEach((l) => l());
  }
  async refresh() {
    const rev = ++this.revision;
    this.set({ ...this.value, loading: true, error: null });
    try {
      await this.services.initializeHome();
      const data = await this.services.network();
      if (rev !== this.revision) return;
      const active = data.memberships.filter((m) => m.status === "active");
      const selected =
        active.find((m) => m.church_id === this.value.viewedChurchId) ||
        active.find((m) => m.is_primary) ||
        active[0];
      this.set({
        data,
        viewedChurchId: selected?.church_id || null,
        loading: false,
        error: null,
      });
    } catch (error) {
      if (rev === this.revision)
        this.set({
          ...this.value,
          loading: false,
          error:
            error instanceof Error
              ? error.message
              : "Could not load your churches.",
        });
    }
  }
  selectChurch(id: string) {
    if (
      !this.value.data?.memberships.some(
        (m) => m.church_id === id && m.status === "active",
      )
    )
      throw new Error("Choose an active membership.");
    this.set({ ...this.value, viewedChurchId: id });
  }
  async setHome(id: string) {
    await this.services.setHome(id);
    await this.refresh();
  }
  dispose() {
    ++this.revision;
  }
}
