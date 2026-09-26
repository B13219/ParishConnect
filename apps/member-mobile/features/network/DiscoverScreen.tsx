import { useRef, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { router } from "expo-router";
import {
  Action,
  Body,
  Button,
  Field,
  Notice,
  Screen,
  styles,
} from "../../components/ui";
import { ChurchCard } from "../../components/ChurchCard";
import { DENOMINATIONS } from "../../constants/denominations";
import { colors } from "../../constants/theme";
import { useServices } from "../../providers/SessionProvider";
import { useLoad } from "../../hooks/useLoad";
import type { Church, DiscoveryFilters } from "../../types/api";

export default function DiscoverScreen() {
  const services = useServices();
  const [draft, setDraft] = useState<DiscoveryFilters>({ view: "all" });
  const [filters, setFilters] = useState<DiscoveryFilters>({ view: "all" });
  const [extra, setExtra] = useState<Church[]>([]);
  const [more, setMore] = useState<boolean | null>(null);
  const [advanced, setAdvanced] = useState(false);
  const [customDenomination, setCustomDenomination] = useState(false);
  const generation = useRef(0);
  const key = JSON.stringify(filters);
  const result = useLoad(key, () => services.discover(filters));

  const reset = () => {
    generation.current++;
    setExtra([]);
    setMore(null);
  };

  const search = () => {
    reset();
    setFilters({ ...draft, country: draft.country?.toUpperCase() });
    result.refresh();
  };

  const selectDenomination = (denomination?: string) => {
    setCustomDenomination(false);
    setDraft({ ...draft, denomination });
  };

  const churches = [...(result.data?.items || []), ...extra];

  return (
    <Screen
      title="Discover churches"
      subtitle="Find community across Tanzania and beyond."
      onRefresh={() => {
        reset();
        result.refresh();
      }}
      refreshing={result.loading}
    >
      <Field
        label="Church name"
        value={draft.q || ""}
        onChangeText={(q) => setDraft({ ...draft, q })}
        returnKeyType="search"
        onSubmitEditing={search}
      />

      <View style={styles.row}>
        {(
          [
            ["all", "All"],
            ["tanzania", "Tanzania"],
            ["local", "Local"],
            ["new", "New on VINYRD"],
          ] as const
        ).map(([view, title]) => (
          <Button
            key={view}
            title={title}
            secondary={draft.view !== view}
            onPress={() => setDraft({ ...draft, view })}
          />
        ))}
      </View>

      <Button
        secondary
        title={advanced ? "Hide location filters" : "Location & denomination"}
        onPress={() => setAdvanced(!advanced)}
      />

      {advanced ? (
        <>
          {(
            [
              ["country", "Country code (TZ, KE, UG…)"],
              ["region", "Region"],
              ["city", "City"],
            ] as const
          ).map(([field, label]) => (
            <Field
              key={field}
              label={label}
              value={draft[field] || ""}
              onChangeText={(value) => setDraft({ ...draft, [field]: value })}
              maxLength={field === "country" ? 2 : 100}
            />
          ))}

          <View style={{ gap: 8 }}>
            <Text style={{ color: colors.text, fontWeight: "500" }}>
              Denomination
            </Text>
            <ScrollView
              horizontal
              nestedScrollEnabled
              contentContainerStyle={{ gap: 10, paddingBottom: 4 }}
              accessibilityLabel="Denomination choices"
            >
              <Button
                title="All denominations"
                secondary={Boolean(draft.denomination) || customDenomination}
                onPress={() => selectDenomination(undefined)}
              />
              {DENOMINATIONS.map((option) => (
                <Button
                  key={option.value}
                  title={option.label}
                  secondary={
                    customDenomination || draft.denomination !== option.value
                  }
                  onPress={() => selectDenomination(option.value)}
                />
              ))}
              <Button
                title="Other"
                secondary={!customDenomination}
                onPress={() => {
                  setCustomDenomination(true);
                  setDraft({ ...draft, denomination: "" });
                }}
              />
            </ScrollView>
            {customDenomination ? (
              <Field
                label="Other denomination"
                value={draft.denomination || ""}
                onChangeText={(denomination) =>
                  setDraft({ ...draft, denomination })
                }
                maxLength={120}
                autoCapitalize="words"
              />
            ) : null}
          </View>
        </>
      ) : null}

      {draft.view === "local" ? (
        <Body>Choose a region or city using Location & denomination.</Body>
      ) : null}

      <Button title="Search churches" onPress={search} />
      <Button
        secondary
        title="Followed churches"
        onPress={() => router.push("/following")}
      />

      <Notice message={result.error} />
      {result.error ? (
        <Button title="Retry search" secondary onPress={result.refresh} />
      ) : null}
      {!result.loading && !result.error && !churches.length ? (
        <Body>No published churches match. Try a broader location.</Body>
      ) : null}

      {churches.map((church) => (
        <ChurchCard key={church.church_id} church={church} />
      ))}

      {(more ?? result.data?.has_more) ? (
        <Action
          title="Load more"
          run={async () => {
            const rev = generation.current;
            const page = await services.discover(filters, churches.length);
            if (rev === generation.current) {
              setExtra([...extra, ...page.items]);
              setMore(page.has_more);
            }
          }}
        />
      ) : null}
    </Screen>
  );
}
