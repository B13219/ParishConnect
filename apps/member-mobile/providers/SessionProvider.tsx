import {
  createContext,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
  type PropsWithChildren,
} from "react";
import { ApiClient } from "../services/api";
import { SessionController } from "../services/session";
import { tokenStorage } from "../services/secureStorage";
import { createServices } from "../services/endpoints";
const Context = createContext<SessionController | null>(null);
export function SessionProvider({ children }: PropsWithChildren) {
  const [controller] = useState(
    () =>
      new SessionController(
        new ApiClient(
          process.env.EXPO_PUBLIC_VINYRD_API_BASE || "",
          fetch,
          __DEV__,
        ),
        tokenStorage,
      ),
  );
  useEffect(() => {
    void controller.restore();
  }, [controller]);
  return <Context.Provider value={controller}>{children}</Context.Provider>;
}
export function useSession() {
  const controller = useContext(Context);
  if (!controller) throw new Error("SessionProvider missing");
  const session = useSyncExternalStore(
    controller.subscribe,
    controller.snapshot,
  );
  return { controller, session };
}
export function useServices() {
  const { controller } = useSession();
  const [services] = useState(() => createServices(controller.api));
  return services;
}
