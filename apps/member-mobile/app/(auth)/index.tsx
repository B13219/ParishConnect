import { router } from "expo-router";
import {
  Body,
  Button,
  Card,
  Heading,
  Notice,
  Screen,
} from "../../components/ui";
import { useSession } from "../../providers/SessionProvider";
export default function Welcome() {
  const { session } = useSession();
  return (
    <Screen
      title="Rooted in faith. Connected in life."
      subtitle="Your church community, wherever you are."
    >
      <Notice message={session.message} />
      <Card>
        <Heading>One account. Many connections.</Heading>
        <Body>
          Find a church, follow its public updates and grow with your community.
          You can join VINYRD before choosing a church.
        </Body>
        <Button
          title="Create account"
          onPress={() => router.push("/register")}
        />
        <Button
          title="Sign in"
          secondary
          onPress={() => router.push("/login")}
        />
      </Card>
    </Screen>
  );
}
