import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { SessionProvider, useSession } from "../providers/SessionProvider";
import { Button, Loading, Notice, Screen } from "../components/ui";
import { colors } from "../constants/theme";
function Navigation() {
  const { session, controller } = useSession();
  if (session.status === "restoring")
    return (
      <Screen title="Welcome to VINYRD">
        <Loading />
      </Screen>
    );
  if (session.status === "error")
    return (
      <Screen title="Reconnect to VINYRD">
        <Notice message={session.message} />
        <Button
          title="Retry session"
          onPress={() => void controller.restore()}
        />
        <Button
          title="Sign out on this device"
          secondary
          onPress={() => void controller.logout()}
        />
      </Screen>
    );
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.cream },
        }}
      >
        <Stack.Protected guard={session.status === "anonymous"}>
          <Stack.Screen name="(auth)" />
        </Stack.Protected>
        <Stack.Protected guard={session.status === "authenticated"}>
          <Stack.Screen name="(member)" />
        </Stack.Protected>
      </Stack>
    </>
  );
}
export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <SessionProvider>
        <Navigation />
      </SessionProvider>
    </SafeAreaProvider>
  );
}
