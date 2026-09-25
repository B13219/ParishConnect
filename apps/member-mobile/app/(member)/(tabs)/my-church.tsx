import { useCallback } from "react";
import { router, useFocusEffect } from "expo-router";
import {
  Action,
  Body,
  Button,
  Card,
  Heading,
  Loading,
  Notice,
  Screen,
  date,
} from "../../../components/ui";
import { useNetwork } from "../../../providers/NetworkProvider";
export default function MyChurch() {
  const { data, viewedChurchId, controller, loading, error } = useNetwork();
  useFocusEffect(
    useCallback(() => {
      void controller.refresh();
    }, [controller]),
  );
  return (
    <Screen
      title="My Church"
      subtitle="Your memberships, your Home Church, your choice."
      refreshing={loading}
      onRefresh={() => void controller.refresh()}
    >
      <Body>
        Viewing a church does not change Home Church. Changing Home Church never
        leaves your other memberships.
      </Body>
      <Notice message={error} />
      {loading && !data ? <Loading /> : null}
      {data?.memberships.length === 0 ? (
        <Card>
          <Body>
            No memberships yet. Discover churches and request to join when you
            are ready.
          </Body>
          <Button
            title="Discover churches"
            onPress={() => router.push("/discover")}
          />
        </Card>
      ) : null}
      {data?.memberships.map((m) => (
        <Card key={m.id}>
          <Heading>{m.church_name}</Heading>
          <Body>
            {m.status}
            {m.is_primary ? " · Home Church" : ""}
            {m.church_id === viewedChurchId ? " · Currently viewing" : ""}
          </Body>
          {m.status === "active" ? (
            <>
              <Button
                title={
                  m.church_id === viewedChurchId
                    ? "Currently viewing"
                    : "View this church"
                }
                secondary
                disabled={m.church_id === viewedChurchId}
                onPress={() => controller.selectChurch(m.church_id)}
              />
              {!m.is_primary ? (
                <Action
                  title="Make Home Church"
                  run={() => controller.setHome(m.id)}
                />
              ) : null}
            </>
          ) : null}
          <Button
            title="Public church profile"
            secondary
            onPress={() =>
              router.push({
                pathname: "/church/[id]",
                params: { id: m.church_id },
              })
            }
          />
        </Card>
      ))}
      <Heading>Membership requests</Heading>
      {data && !data.requests.length ? <Body>No requests yet.</Body> : null}
      {data?.requests.map((r) => (
        <Card key={r.id}>
          <Heading>
            {data.memberships.find((m) => m.church_id === r.church_id)
              ?.church_name || "Church membership request"}
          </Heading>
          <Body>
            {r.status.replaceAll("_", " ")} · {date(r.created_at)}
          </Body>
          {r.rejection_reason ? <Body>{r.rejection_reason}</Body> : null}
          <Button
            title="View request"
            secondary
            onPress={() =>
              router.push({
                pathname: "/membership/[id]",
                params: { id: r.church_id },
              })
            }
          />
        </Card>
      ))}
    </Screen>
  );
}
