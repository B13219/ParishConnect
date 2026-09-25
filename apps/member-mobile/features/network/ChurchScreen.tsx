import { Image, Linking } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
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
} from "../../components/ui";
import { useServices } from "../../providers/SessionProvider";
import { useNetwork } from "../../providers/NetworkProvider";
import { useLoad } from "../../hooks/useLoad";
export default function ChurchScreen() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const services = useServices();
  const { data, controller, error } = useNetwork();
  const result = useLoad("church:" + id, () => services.church(id));
  const church = result.data;
  const following = data?.follows.includes(id) || false;
  return (
    <Screen
      title={church?.name || "Church profile"}
      subtitle={
        church
          ? [church.city, church.region, church.country]
              .filter(Boolean)
              .join(" · ")
          : "Public church life"
      }
      onRefresh={() => {
        result.refresh();
        void controller.refresh();
      }}
      refreshing={result.loading}
    >
      <Notice message={result.error} />
      {result.loading ? <Loading /> : null}
      {result.error ? <Button title="Retry" onPress={result.refresh} /> : null}
      {church ? (
        <>
          {church.logo_url?.startsWith("https://") ? (
            <Image
              source={{ uri: church.logo_url }}
              accessibilityLabel="Church logo"
              style={{ width: 90, height: 90, borderRadius: 22 }}
            />
          ) : null}
          <Card>
            {church.denomination ? <Body>{church.denomination}</Body> : null}
            {church.about ? <Body>{church.about}</Body> : null}
            {church.location ? <Body>{church.location}</Body> : null}
            {church.service_times ? (
              <>
                <Heading>Service times</Heading>
                <Body>{church.service_times}</Body>
              </>
            ) : null}
          </Card>
          <Card>
            <Heading>Follow this church</Heading>
            <Body>Receive its public updates without joining as a member.</Body>
            <Notice message={error} />
            <Action
              title={following ? "Unfollow" : "Follow"}
              disabled={!data}
              run={async () => {
                await services.follow(id, !following);
                await controller.refresh();
              }}
            />
          </Card>
          <Card>
            <Heading>Church membership</Heading>
            <Body>
              {data?.memberships.find((m) => m.church_id === id)?.status ===
              "active"
                ? "Your membership is approved."
                : "Join this community through church review."}
            </Body>
            <Button
              title={
                data?.requests.some((r) => r.church_id === id) ||
                data?.memberships.some((m) => m.church_id === id)
                  ? "Membership & request status"
                  : "Request to join"
              }
              onPress={() =>
                router.push({ pathname: "/membership/[id]", params: { id } })
              }
            />
          </Card>
          {(
            [
              ["Public events", church.public_events],
              ["Announcements", church.public_announcements],
              ["Ministries", church.public_ministries],
            ] as const
          ).map(([title, items]) =>
            items.length ? (
              <Card key={title}>
                <Heading>{title}</Heading>
                {items.map((item, i) => (
                  <Card key={i}>
                    <Heading>{item.title}</Heading>
                    <Body>{item.body}</Body>
                    {item.starts_at ? (
                      <Body>{date(item.starts_at)}</Body>
                    ) : null}
                    {item.location ? <Body>{item.location}</Body> : null}
                  </Card>
                ))}
              </Card>
            ) : null,
          )}
          {church.contact_email || church.contact_phone || church.website ? (
            <Card>
              <Heading>Public contact</Heading>
              {church.contact_email ? (
                <Body>{church.contact_email}</Body>
              ) : null}
              {church.contact_phone ? (
                <Body>{church.contact_phone}</Body>
              ) : null}
              {church.website?.startsWith("https://") ? (
                <Action
                  secondary
                  title="Open church website"
                  run={() => Linking.openURL(church.website!)}
                />
              ) : null}
            </Card>
          ) : null}
        </>
      ) : null}
    </Screen>
  );
}
