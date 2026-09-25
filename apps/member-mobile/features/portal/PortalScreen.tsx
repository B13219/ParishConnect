import { useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
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
import { ChurchContext } from "../../components/ChurchContext";
import { useNetwork } from "../../providers/NetworkProvider";
import { useServices } from "../../providers/SessionProvider";
import { useLoad } from "../../hooks/useLoad";
import type {
  Event,
  PortalHome,
  Groups,
  Message,
  Prayer,
  Sermon,
  Lesson,
} from "../../types/api";
type Data =
  | { kind: "events"; rows: Event[] }
  | { kind: "giving"; home: PortalHome }
  | { kind: "groups"; groups: Groups }
  | { kind: "messages"; rows: Message[] }
  | { kind: "prayer"; rows: Prayer[] }
  | { kind: "sermons"; rows: Sermon[]; lessons: Lesson[] };
const titles: Record<string, string> = {
  events: "Events",
  giving: "My giving",
  groups: "My groups",
  messages: "Messages",
  prayer: "Prayer",
  sermons: "Sermons & Bible",
};
function PrayerForm({
  churchId,
  onSaved,
}: {
  churchId: string;
  onSaved: () => void;
}) {
  const services = useServices();
  const [body, setBody] = useState("");
  const [contact, setContact] = useState(false);
  const [share, setShare] = useState(false);
  return (
    <Card>
      <Heading>Share a prayer request</Heading>
      <Field
        label="Prayer request"
        value={body}
        onChangeText={setBody}
        maxLength={2000}
        multiline
      />
      <Toggle
        label="Pastoral team may contact me"
        value={contact}
        onChange={setContact}
      />
      <Toggle
        label="Allow the church to share this prayer"
        value={share}
        onChange={setShare}
      />
      <Body>
        {share
          ? "This prayer may be shared by the church."
          : "Visible to the pastoral team."}
      </Body>
      <Action
        title="Send prayer request"
        run={async () => {
          if (body.trim().length < 3)
            throw new Error("Please write at least three characters.");
          await services.sendPrayer(churchId, {
            body,
            category: "general",
            visibility: share ? "shareable" : "pastoral_team",
            allow_contact: contact,
          });
          setBody("");
          onSaved();
        }}
      />
    </Card>
  );
}
export default function PortalScreen() {
  const { section } = useLocalSearchParams<{ section: string }>();
  const { viewedChurchId, data: network } = useNetwork();
  const services = useServices();
  const result = useLoad<Data>(
    section + ":" + viewedChurchId,
    async () => {
      const id = viewedChurchId!;
      switch (section) {
        case "events":
          return { kind: "events", rows: await services.events(id) };
        case "giving":
          return { kind: "giving", home: await services.home(id) };
        case "groups":
          return { kind: "groups", groups: await services.groups(id) };
        case "messages":
          return { kind: "messages", rows: await services.messages(id) };
        case "prayer":
          return { kind: "prayer", rows: await services.prayers(id) };
        case "sermons": {
          const [rows, lessons] = await Promise.all([
            services.sermons(id),
            services.lessons(id),
          ]);
          return { kind: "sermons", rows, lessons };
        }
        default:
          throw new Error("This church feature was not found.");
      }
    },
    Boolean(viewedChurchId),
  );
  const data = viewedChurchId ? result.data : undefined;
  return (
    <Screen
      title={titles[section] || "Church life"}
      onRefresh={result.refresh}
      refreshing={result.loading && !!viewedChurchId}
    >
      <ChurchContext />
      {!viewedChurchId ? (
        <Card>
          <Body>
            {network
              ? "An approved active membership is needed for this church feature. Your VINYRD account remains available."
              : "Loading your church memberships…"}
          </Body>
          <Button title="My Church" onPress={() => router.push("/my-church")} />
        </Card>
      ) : null}
      <Notice message={result.error} />
      {result.error ? <Button title="Retry" onPress={result.refresh} /> : null}
      {result.loading && viewedChurchId ? <Loading /> : null}
      {data?.kind === "events" ? (
        <>
          {!data.rows.length ? <Body>No church events yet.</Body> : null}
          {data.rows.map((event) => (
            <Card key={event.id}>
              <Heading>{event.name}</Heading>
              <Body>{date(event.starts_at)}</Body>
              {event.location ? <Body>{event.location}</Body> : null}
              <Body>{event.checked_in ? "Checked in" : "Not checked in"}</Body>
            </Card>
          ))}
          <Body>
            Mobile QR and location check-in are not enabled in this foundation.
          </Body>
        </>
      ) : null}
      {data?.kind === "giving" ? (
        <>
          <Card>
            <Heading>
              {data.home.giving.currency + " " + data.home.giving.total_amount}
            </Heading>
            <Body>Total recorded giving for this church.</Body>
          </Card>
          <Heading>Recent giving</Heading>
          {!data.home.giving.latest.length ? (
            <Body>No giving records yet.</Body>
          ) : null}
          {data.home.giving.latest.map((item) => (
            <Card key={item.id}>
              <Heading>{item.currency + " " + item.amount}</Heading>
              <Body>{item.type + " · " + date(item.received_at)}</Body>
              <Body>{item.payment_method.replaceAll("_", " ")}</Body>
            </Card>
          ))}
          <Body>
            This is your recorded giving history. Payment collection is not
            enabled in the mobile foundation.
          </Body>
        </>
      ) : null}
      {data?.kind === "groups" ? (
        <>
          {[...data.groups.communities, ...data.groups.ministries].length ===
          0 ? (
            <Body>You have no group or ministry memberships here yet.</Body>
          ) : null}
          <Heading>{data.groups.community_label}</Heading>
          {data.groups.communities.map((group) => (
            <Card key={group.id}>
              <Heading>{group.name}</Heading>
              <Body>{group.role}</Body>
              {group.meeting_day ? <Body>{group.meeting_day}</Body> : null}
              {group.leader_name ? (
                <Body>{"Leader: " + group.leader_name}</Body>
              ) : null}
            </Card>
          ))}
          <Heading>Ministries</Heading>
          {data.groups.ministries.map((group) => (
            <Card key={group.id}>
              <Heading>{group.name}</Heading>
              <Body>{group.role}</Body>
            </Card>
          ))}
        </>
      ) : null}
      {data?.kind === "messages" ? (
        <>
          {!data.rows.length ? <Body>No messages yet.</Body> : null}
          {data.rows.map((message) => (
            <Card key={message.id}>
              <Heading>{message.subject || "Church message"}</Heading>
              <Body>{message.body}</Body>
              <Body>{date(message.sent_at)}</Body>
            </Card>
          ))}
        </>
      ) : null}
      {data?.kind === "prayer" ? (
        <>
          <PrayerForm
            key={viewedChurchId}
            churchId={viewedChurchId!}
            onSaved={result.refresh}
          />
          <Heading>Your requests</Heading>
          {!data.rows.length ? <Body>No prayer requests yet.</Body> : null}
          {data.rows.map((prayer) => (
            <Card key={prayer.id}>
              <Body>{prayer.body}</Body>
              <Body>{prayer.status + " · " + date(prayer.created_at)}</Body>
            </Card>
          ))}
        </>
      ) : null}
      {data?.kind === "sermons" ? (
        <>
          <Heading>Published sermons</Heading>
          {!data.rows.length ? (
            <Body>No sermons published by this church yet.</Body>
          ) : null}
          {data.rows.map((sermon) => (
            <Card key={sermon.id}>
              <Heading>{sermon.title || sermon.event_name}</Heading>
              {sermon.speaker ? <Body>{sermon.speaker}</Body> : null}
              {sermon.scripture_reference ? (
                <Body>{sermon.scripture_reference}</Body>
              ) : null}
              {sermon.summary ? <Body>{sermon.summary}</Body> : null}
            </Card>
          ))}
          <Heading>My sermon lessons</Heading>
          {data.lessons.map((lesson) => (
            <Card key={lesson.id}>
              <Heading>{lesson.sermon_title}</Heading>
              {lesson.scripture_reference ? (
                <Body>{lesson.scripture_reference}</Body>
              ) : null}
              <Body>{lesson.key_lesson}</Body>
              {lesson.action_point ? <Body>{lesson.action_point}</Body> : null}
            </Card>
          ))}
          <Body>
            Bible references appear with published sermons and your lessons. A
            full Bible reader is not included in this phase.
          </Body>
        </>
      ) : null}
    </Screen>
  );
}
