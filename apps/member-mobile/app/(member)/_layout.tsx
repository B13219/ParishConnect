import { Stack } from "expo-router";
import { NetworkProvider } from "../../providers/NetworkProvider";
import { useSession } from "../../providers/SessionProvider";
import { colors } from "../../constants/theme";
export default function MemberLayout() {
  const { session } = useSession();
  return (
    <NetworkProvider key={session.user?.id}>
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.ink },
          headerTintColor: colors.paper,
          headerBackTitle: "Back",
          title: "VINYRD",
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="onboarding" options={{ headerShown: false }} />
        <Stack.Screen name="account" options={{ title: "Your account" }} />
        <Stack.Screen
          name="church/[id]"
          options={{ title: "Church profile" }}
        />
        <Stack.Screen
          name="membership/[id]"
          options={{ title: "Membership" }}
        />
        <Stack.Screen
          name="portal/[section]"
          options={{ title: "My church" }}
        />
      </Stack>
    </NetworkProvider>
  );
}
