import { Redirect, router } from "expo-router";
import {
  Body,
  Button,
  Card,
  Heading,
  Notice,
  Screen,
} from "../../../components/ui";
import { ChurchContext } from "../../../components/ChurchContext";
import { useSession } from "../../../providers/SessionProvider";
import { useNetwork } from "../../../providers/NetworkProvider";
export default function Home() {
  const { session } = useSession();
  const { data, error, controller, loading } = useNetwork();
  if (session.onboarding) return <Redirect href="/onboarding" />;
  const active = data?.memberships.filter((m) => m.status === "active") || [];
  return (
    <Screen
      title={"Welcome, " + (session.user?.name.split(" ")[0] || "friend")}
      subtitle="People. Purpose. A brighter tomorrow."
      onRefresh={() => void controller.refresh()}
      refreshing={loading}
    >
      <Notice message={error} />
      {active.length ? (
        <ChurchContext />
      ) : (
        <Card>
          <Heading>Your VINYRD begins here</Heading>
          <Body>
            You can discover and follow churches while your membership is being
            reviewed. Your account is ready to use.
          </Body>
          <Button
            title="Find your community"
            onPress={() => router.push("/discover")}
          />
        </Card>
      )}
      <Card>
        <Heading>Stay connected</Heading>
        <Body>
          {active.length +
            " active church memberships · " +
            (data?.follows.length || 0) +
            " churches followed"}
        </Body>
        <Button
          title="My Church & requests"
          secondary
          onPress={() => router.push("/my-church")}
        />
      </Card>
      <Heading>Your church life</Heading>
      {(
        [
          ["events", "Events"],
          ["giving", "Giving"],
          ["groups", "Groups"],
          ["messages", "Messages"],
          ["prayer", "Prayer"],
          ["sermons", "Sermons & Bible"],
        ] as const
      ).map(([section, label]) => (
        <Button
          key={section}
          title={label}
          secondary
          onPress={() =>
            router.push({ pathname: "/portal/[section]", params: { section } })
          }
        />
      ))}
      <Body>
        Private church features require an approved active membership. Following
        never grants that access.
      </Body>
    </Screen>
  );
}
