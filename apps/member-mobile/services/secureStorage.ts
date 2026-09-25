import * as SecureStore from "expo-secure-store";
import type { TokenStorage } from "./session";
const KEY = "vinyrd.member.access-token.v1";
const options = {
  keychainService: "app.vinyrd.member.session",
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};
export const tokenStorage: TokenStorage = {
  read: () => SecureStore.getItemAsync(KEY, options),
  write: (token) => SecureStore.setItemAsync(KEY, token, options),
  remove: () => SecureStore.deleteItemAsync(KEY, options),
};
