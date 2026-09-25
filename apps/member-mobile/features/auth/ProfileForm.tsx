import { useState } from "react";
import { router } from "expo-router";
import {
  Action,
  Body,
  Button,
  Field,
  Loading,
  Notice,
  Screen,
} from "../../components/ui";
import { useLoad } from "../../hooks/useLoad";
import { useServices, useSession } from "../../providers/SessionProvider";
import type { ProfileInput } from "../../types/api";
const fields = [
  ["first_name", "First name", 80],
  ["last_name", "Last name", 79],
  ["phone", "Phone (optional)", 40],
  ["country", "Country (optional)", 100],
  ["region", "Region (optional)", 100],
  ["city", "City (optional)", 100],
  ["avatar_url", "Profile photo HTTPS URL (optional)", 2048],
] as const;
export default function ProfileForm({
  onboarding = false,
}: {
  onboarding?: boolean;
}) {
  const services = useServices();
  const { controller } = useSession();
  const result = useLoad("profile-edit", services.profile);
  const [draft, setForm] = useState<ProfileInput | null>(null);
  const [saved, setSaved] = useState(false);
  const form =
    draft ||
    (result.data
      ? {
          first_name: result.data.first_name,
          last_name: result.data.last_name,
          phone: result.data.phone,
          country: result.data.country,
          region: result.data.region,
          city: result.data.city,
          avatar_url: result.data.avatar_url,
        }
      : null);
  const finish = () => {
    controller.completeOnboarding();
    router.replace("/(member)/(tabs)");
  };
  return (
    <Screen
      title={onboarding ? "Make yourself at home" : "Your global profile"}
      subtitle="Your profile belongs to you. Sharing contact details with a church is a separate choice."
    >
      {result.loading ? <Loading /> : null}
      <Notice message={result.error} />
      {result.error ? <Button title="Retry" onPress={result.refresh} /> : null}
      {form
        ? fields.map(([key, label, max]) => (
            <Field
              key={key}
              label={label}
              value={form[key] || ""}
              onChangeText={(value) => {
                setSaved(false);
                setForm({ ...form, [key]: value });
              }}
              maxLength={max}
              keyboardType={key === "phone" ? "phone-pad" : "default"}
              autoCapitalize={key === "avatar_url" ? "none" : "words"}
            />
          ))
        : null}
      {form ? (
        <Action
          title="Save profile"
          run={async () => {
            if (!form.first_name.trim() || !form.last_name.trim())
              throw new Error("First and last names are required.");
            await services.updateProfile({
              ...form,
              phone: form.phone || null,
              avatar_url: form.avatar_url || null,
              country: form.country || null,
              region: form.region || null,
              city: form.city || null,
            });
            setSaved(true);
            if (onboarding) finish();
          }}
        />
      ) : null}
      {saved ? <Body>Profile saved.</Body> : null}
      {onboarding ? (
        <Button secondary title="Skip for now" onPress={finish} />
      ) : null}
    </Screen>
  );
}
