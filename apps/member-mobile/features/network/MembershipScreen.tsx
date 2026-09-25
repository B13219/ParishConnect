import { useCallback, useState } from "react";
import { router, useFocusEffect, useLocalSearchParams } from "expo-router";
import {
  Action,
  Body,
  Button,
  Card,
  Field,
  Heading,
  Loading,
  Notice,
  Screen,
  Toggle,
  date,
} from "../../components/ui";
import { useNetwork } from "../../providers/NetworkProvider";
import { useServices } from "../../providers/SessionProvider";
export default function MembershipScreen() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { data, controller, error, loading } = useNetwork();
  const services = useServices();
  const [message, setMessage] = useState("");
  const [share, setShare] = useState(false);
  useFocusEffect(
    useCallback(() => {
      void controller.refresh();
    }, [controller]),
  );
  const membership = data?.memberships.find((m) => m.church_id === id);
  const history = data?.requests.filter((r) => r.church_id === id) || [];
  const open = history.find((r) =>
    ["pending", "more_info_required"].includes(r.status),
  );
  const active = membership?.status === "active";
  return (
    <Screen
      title={membership?.church_name || "Church membership"}
      subtitle="Membership is reviewed by this church. Your global account stays yours."
      onRefresh={() => void controller.refresh()}
      refreshing={loading}
    >
      <Notice message={error} />
      {!data ? (
        <>
          <Loading />
          <Button
            secondary
            title="Retry"
            onPress={() => void controller.refresh()}
          />
        </>
      ) : null}
      {active ? (
        <Card>
          <Heading>Approved membership</Heading>
          <Body>
            {membership.is_primary
              ? "This is your Home Church."
              : "Active church membership."}
          </Body>
          <Button
            title="View this church"
            onPress={() => {
              controller.selectChurch(id);
              router.push("/my-church");
            }}
          />
          {!membership.is_primary ? (
            <Action
              title="Make Home Church"
              run={() => controller.setHome(membership.id)}
            />
          ) : null}
        </Card>
      ) : membership?.status === "suspended" ? (
        <Body>Your membership is suspended. Contact the church office.</Body>
      ) : open ? (
        <Card>
          <Heading>
            {open.status === "pending"
              ? "Pending review"
              : "More information requested"}
          </Heading>
          {open.rejection_reason ? <Body>{open.rejection_reason}</Body> : null}
          <Body>
            You can contact the church or cancel and submit a new request with
            more information.
          </Body>
          <Action
            secondary
            title="Cancel request"
            run={async () => {
              await services.cancel(open.id);
              await controller.refresh();
            }}
          />
        </Card>
      ) : data ? (
        <Card>
          <Heading>Request to join</Heading>
          <Body>
            Your name and introduction will be shared with this church’s
            reviewers.
          </Body>
          <Field
            label="Introduce yourself (optional)"
            multiline
            value={message}
            onChangeText={setMessage}
            maxLength={2000}
          />
          <Toggle
            label="Also share my email, phone and profile photo with reviewers"
            value={share}
            onChange={setShare}
          />
          <Action
            title="Send membership request"
            run={async () => {
              await services.join(id, message, share);
              setMessage("");
              await controller.refresh();
            }}
          />
        </Card>
      ) : null}
      {history.length ? <Heading>Request history</Heading> : null}
      {history.map((r) => (
        <Card key={r.id}>
          <Heading>{r.status.replaceAll("_", " ")}</Heading>
          <Body>{date(r.created_at)}</Body>
          {r.message ? <Body>{r.message}</Body> : null}
          {r.rejection_reason ? <Body>{r.rejection_reason}</Body> : null}
          {r.status === "rejected" ? (
            <Body>
              This does not remove your VINYRD account or your follows. You can
              request membership elsewhere.
            </Body>
          ) : null}
        </Card>
      ))}
    </Screen>
  );
}
