import { router } from "expo-router";
import { Body, Button, Card } from "./ui";
import { useNetwork } from "../providers/NetworkProvider";
export function ChurchContext() {
  const { data, viewedChurchId } = useNetwork();
  const current = data?.memberships.find((m) => m.church_id === viewedChurchId);
  return (
    <Card>
      <Body>
        {current
          ? "Viewing " + current.church_name
          : "No active church selected"}
      </Body>
      <Body>Viewing a church is separate from Home Church.</Body>
      <Button
        secondary
        title="Choose church"
        onPress={() => router.push("/my-church")}
      />
    </Card>
  );
}
