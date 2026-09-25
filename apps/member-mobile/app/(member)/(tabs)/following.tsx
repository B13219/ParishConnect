import { useCallback } from "react";
import { router, useFocusEffect } from "expo-router";
import { Body, Button, Notice, Screen } from "../../../components/ui";
import { useNetwork } from "../../../providers/NetworkProvider";
import FollowedChurch from "../../../features/network/FollowedChurch";
export default function Following() {
  const { data, controller, loading, error } = useNetwork();
  useFocusEffect(
    useCallback(() => {
      void controller.refresh();
    }, [controller]),
  );
  return (
    <Screen
      title="Following"
      subtitle="Stay close to public church life. Following is separate from membership."
      refreshing={loading}
      onRefresh={() => void controller.refresh()}
    >
      <Notice message={error} />
      {data && !data.follows.length ? (
        <Body>You are not following any churches yet.</Body>
      ) : null}
      {data?.follows.map((id) => (
        <FollowedChurch key={id} id={id} />
      ))}
      <Button
        title="Discover churches"
        onPress={() => router.push("/discover")}
      />
    </Screen>
  );
}
