import { Image } from "react-native";
import { router } from "expo-router";
import type { Church } from "../types/api";
import { Body, Button, Card, Heading } from "./ui";
export function ChurchCard({ church }: { church: Church }) {
  return (
    <Card>
      {church.logo_url?.startsWith("https://") ? (
        <Image
          source={{ uri: church.logo_url }}
          style={{ width: 64, height: 64, borderRadius: 16 }}
          accessibilityLabel={church.name + " logo"}
        />
      ) : null}
      <Heading>{church.name}</Heading>
      <Body>
        {[church.city, church.region, church.country]
          .filter(Boolean)
          .join(" · ")}
      </Body>
      {church.denomination ? <Body>{church.denomination}</Body> : null}
      <Button
        title="View church"
        secondary
        onPress={() =>
          router.push({
            pathname: "/church/[id]",
            params: { id: church.church_id },
          })
        }
      />
    </Card>
  );
}
