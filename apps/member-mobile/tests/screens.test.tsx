import { useEffect } from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import AuthForm from "../features/auth/AuthForm";
import MembershipScreen from "../features/network/MembershipScreen";
import Home from "../app/(member)/(tabs)/index";
import { useSession, useServices } from "../providers/SessionProvider";
import { useNetwork } from "../providers/NetworkProvider";
import { useLoad } from "../hooks/useLoad";
import type { Network } from "../types/api";
jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn() },
  Redirect: () => null,
  useLocalSearchParams: () => ({ id: "a" }),
  useFocusEffect: (effect: () => void) => {
    jest.requireActual("react").useEffect(effect, [effect]);
  },
}));
jest.mock(
  "react-native-safe-area-context",
  () => jest.requireActual("react-native-safe-area-context/jest/mock").default,
);
jest.mock("../providers/SessionProvider");
jest.mock("../providers/NetworkProvider");
const authenticate = jest.fn(async () => {});
const join = jest.fn(async () => {});
const refresh = jest.fn(async () => {});
const selectChurch = jest.fn();
const setHome = jest.fn(async () => {});
const state: Network = { memberships: [], requests: [], follows: [] };
beforeEach(() => {
  jest
    .mocked(useSession)
    .mockReturnValue({
      session: {
        status: "authenticated",
        user: {
          id: "u",
          name: "Ada",
          email: "a@test.local",
          phone: null,
          roles: [],
        },
        message: null,
      },
      controller: { authenticate } as unknown as ReturnType<
        typeof useSession
      >["controller"],
    });
  jest
    .mocked(useServices)
    .mockReturnValue({ join } as unknown as ReturnType<typeof useServices>);
  jest
    .mocked(useNetwork)
    .mockReturnValue({
      data: state,
      viewedChurchId: null,
      loading: false,
      error: null,
      controller: { refresh, selectChurch, setHome } as unknown as ReturnType<
        typeof useNetwork
      >["controller"],
    });
});
test("native registration form calls registration with the entered fields", async () => {
  const ui = await render(<AuthForm register />);
  await fireEvent.changeText(ui.getByLabelText("First name"), "Ada");
  await fireEvent.changeText(ui.getByLabelText("Last name"), "Person");
  await fireEvent.changeText(ui.getByLabelText("Email"), "ada@example.test");
  await fireEvent.changeText(
    ui.getByLabelText("Password"),
    "long-test-password",
  );
  await fireEvent.press(ui.getByText("Create VINYRD account"));
  await waitFor(() =>
    expect(authenticate).toHaveBeenCalledWith("register", {
      first_name: "Ada",
      last_name: "Person",
      email: "ada@example.test",
      password: "long-test-password",
    }),
  );
});
test("native login does not ask for a member or church ID", async () => {
  const ui = await render(<AuthForm />);
  await fireEvent.changeText(ui.getByLabelText("Email"), "ada@example.test");
  await fireEvent.changeText(ui.getByLabelText("Password"), "secret");
  await fireEvent.press(ui.getByText("Sign in"));
  await waitFor(() =>
    expect(authenticate).toHaveBeenCalledWith("login", {
      email: "ada@example.test",
      password: "secret",
    }),
  );
  expect(ui.queryByLabelText("Church")).toBeNull();
});
test("zero-membership home stays usable and offers discovery", async () => {
  const ui = await render(<Home />);
  expect(ui.getByText("Your VINYRD begins here")).toBeTruthy();
  expect(ui.getByText("Find your community")).toBeTruthy();
});
test("native request form shares contacts only after explicit opt-in", async () => {
  const ui = await render(<MembershipScreen />);
  await fireEvent.changeText(
    ui.getByLabelText("Introduce yourself (optional)"),
    "Hello church",
  );
  await fireEvent.press(ui.getByText("Send membership request"));
  await waitFor(() =>
    expect(join).toHaveBeenCalledWith("a", "Hello church", false),
  );
});
test.each(["pending", "more_info_required", "rejected"] as const)(
  "native request status displays %s without granting membership",
  async (status) => {
    jest
      .mocked(useNetwork)
      .mockReturnValue({
        ...useNetwork(),
        data: {
          ...state,
          requests: [
            {
              id: "r",
              church_id: "a",
              status,
              created_at: "2026-09-25",
              message: null,
              rejection_reason: "Contact the office",
            },
          ],
        },
      });
    const ui = await render(<MembershipScreen />);
    expect(ui.getAllByText("Contact the office").length).toBeGreaterThan(0);
    expect(ui.queryByText("Approved membership")).toBeNull();
  },
);
test("approved member has distinct view and Home Church actions", async () => {
  jest
    .mocked(useNetwork)
    .mockReturnValue({
      ...useNetwork(),
      data: {
        ...state,
        memberships: [
          {
            id: "ma",
            church_id: "a",
            church_name: "Church A",
            status: "active",
            is_primary: false,
            legacy_member_id: "old",
          },
        ],
      },
    });
  const ui = await render(<MembershipScreen />);
  expect(ui.getByText("Approved membership")).toBeTruthy();
  await fireEvent.press(ui.getByText("View this church"));
  expect(selectChurch).toHaveBeenCalledWith("a");
  expect(setHome).not.toHaveBeenCalled();
  await fireEvent.press(ui.getByText("Make Home Church"));
  expect(setHome).toHaveBeenCalledWith("ma");
});
function Loader({
  church,
  load,
  onState,
}: {
  church: string;
  load: () => Promise<string>;
  onState: (value: string | undefined) => void;
}) {
  const value = useLoad(church, load);
  useEffect(() => {
    onState(value.data);
  }, [value.data, onState]);
  return null;
}
test("private data is cleared immediately on church switch and late responses cannot cross contexts", async () => {
  let finishA!: (value: string) => void;
  let finishB!: (value: string) => void;
  const a = () =>
    new Promise<string>((resolve) => {
      finishA = resolve;
    });
  const b = () =>
    new Promise<string>((resolve) => {
      finishB = resolve;
    });
  const seen = jest.fn();
  const ui = await render(<Loader church="a" load={a} onState={seen} />);
  await ui.rerender(<Loader church="b" load={b} onState={seen} />);
  finishA("Church A giving");
  finishB("Church B giving");
  await waitFor(() => expect(seen).toHaveBeenLastCalledWith("Church B giving"));
  expect(seen).not.toHaveBeenCalledWith("Church A giving");
});
