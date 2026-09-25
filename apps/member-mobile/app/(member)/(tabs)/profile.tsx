import { Image } from "react-native";
import { router } from "expo-router";
import {
  Action,
  Body,
  Button,
  Card,
  Heading,
  Notice,
  Screen,
} from "../../../components/ui";
import { useServices, useSession } from "../../../providers/SessionProvider";
import { useLoad } from "../../../hooks/useLoad";
export default function Account() {
  const services = useServices();
  const { controller, session } = useSession();
  const result = useLoad("profile", services.profile);
  const profile = result.data;
  return (
    <Screen
      title="Your profile"
      subtitle="One VINYRD account, wherever you worship."
      onRefresh={result.refresh}
      refreshing={result.loading}
    >
      <Notice message={result.error} />
      <Card>
        {profile?.avatar_url?.startsWith("https://") ? (
          <Image
            source={{ uri: profile.avatar_url }}
            accessibilityLabel="Your profile photo"
            style={{ width: 80, height: 80, borderRadius: 40 }}
          />
        ) : null}
        <Heading>
          {profile
            ? profile.first_name + " " + profile.last_name
            : session.user?.name}
        </Heading>
        <Body>{profile?.email || session.user?.email}</Body>
        {profile?.phone ? <Body>{profile.phone}</Body> : null}
        {profile ? (
          <Body>
            {[profile.city, profile.region, profile.country]
              .filter(Boolean)
              .join(" · ")}
          </Body>
        ) : null}
        <Button
          title="Edit global profile"
          onPress={() => router.push("/account")}
        />
        <Button
          secondary
          title="Manage my churches"
          onPress={() => router.push("/my-church")}
        />
      </Card>
      <Action
        secondary
        title="Sign out on this device"
        run={() => controller.logout()}
      />
      <Body>
        Signing out does not delete your account, memberships or church history.
      </Body>
    </Screen>
  );
}
