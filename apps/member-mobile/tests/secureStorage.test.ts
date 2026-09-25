import * as SecureStore from "expo-secure-store";
import { tokenStorage } from "../services/secureStorage";
jest.mock("expo-secure-store", () => ({
  WHEN_UNLOCKED_THIS_DEVICE_ONLY: 4,
  getItemAsync: jest.fn(async () => "token"),
  setItemAsync: jest.fn(async () => {}),
  deleteItemAsync: jest.fn(async () => {}),
}));
test("all token operations use SecureStore with the same key/service and device-only accessibility", async () => {
  expect(await tokenStorage.read()).toBe("token");
  await tokenStorage.write("bearer");
  await tokenStorage.remove();
  const key = "vinyrd.member.access-token.v1";
  const options = {
    keychainService: "app.vinyrd.member.session",
    keychainAccessible: 4,
  };
  expect(SecureStore.getItemAsync).toHaveBeenCalledWith(key, options);
  expect(SecureStore.setItemAsync).toHaveBeenCalledWith(key, "bearer", options);
  expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith(key, options);
});
