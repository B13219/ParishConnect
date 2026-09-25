import {
  createContext,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
  type PropsWithChildren,
} from "react";
import { AppState } from "react-native";
import { NetworkController } from "../services/networkState";
import { useServices, useSession } from "./SessionProvider";
const Context = createContext<NetworkController | null>(null);
export function NetworkProvider({ children }: PropsWithChildren) {
  const services = useServices();
  const { controller: session } = useSession();
  const [controller] = useState(() => new NetworkController(services));
  useEffect(() => {
    void controller.refresh();
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active")
        void session.api
          .request("/auth/me")
          .then(() => controller.refresh())
          .catch(() => {});
    });
    return () => {
      sub.remove();
      controller.dispose();
    };
  }, [controller, session]);
  return <Context.Provider value={controller}>{children}</Context.Provider>;
}
export function useNetwork() {
  const controller = useContext(Context);
  if (!controller) throw new Error("NetworkProvider missing");
  const state = useSyncExternalStore(controller.subscribe, controller.snapshot);
  return { controller, ...state };
}
