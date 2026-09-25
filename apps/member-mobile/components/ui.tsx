import { useRef, useState, type PropsWithChildren } from "react";
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
  type TextInputProps,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors } from "../constants/theme";
export const styles = StyleSheet.create({
  title: {
    fontFamily: Platform.OS === "ios" ? "Georgia" : "serif",
    fontSize: 30,
    color: colors.paper,
    lineHeight: 38,
  },
  body: { fontSize: 16, lineHeight: 24, color: colors.secondary },
  heading: {
    fontSize: 20,
    fontWeight: "600",
    color: colors.text,
    lineHeight: 28,
  },
  card: {
    backgroundColor: colors.paper,
    borderRadius: 20,
    padding: 20,
    borderWidth: 1,
    borderColor: colors.line,
    gap: 12,
  },
  row: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
    alignItems: "center",
  },
  input: {
    backgroundColor: colors.paper,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 12,
    padding: 14,
    fontSize: 16,
    color: colors.text,
    minHeight: 50,
  },
});
export function Screen({
  title,
  subtitle,
  children,
  refreshing = false,
  onRefresh,
}: PropsWithChildren<{
  title: string;
  subtitle?: string;
  refreshing?: boolean;
  onRefresh?: () => void;
}>) {
  return (
    <SafeAreaView
      style={{ flex: 1, backgroundColor: colors.ink }}
      edges={["top", "left", "right"]}
    >
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          style={{ backgroundColor: colors.cream }}
          contentContainerStyle={{ paddingBottom: 40 }}
          keyboardShouldPersistTaps="handled"
          refreshControl={
            onRefresh ? (
              <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
            ) : undefined
          }
        >
          <View style={{ backgroundColor: colors.ink, padding: 24, gap: 14 }}>
            <View style={styles.row}>
              <Image
                source={require("../assets/vinyrd-logo.png")}
                accessibilityLabel="VINYRD crest"
                style={{ width: 52, height: 52, borderRadius: 26 }}
              />
              <Text
                style={{
                  color: colors.gold,
                  letterSpacing: 3,
                  fontWeight: "600",
                }}
              >
                VINYRD
              </Text>
            </View>
            <Text accessibilityRole="header" style={styles.title}>
              {title}
            </Text>
            {subtitle ? (
              <Text style={{ color: "#D4DDC9", fontSize: 15, lineHeight: 23 }}>
                {subtitle}
              </Text>
            ) : null}
            <View
              style={{
                backgroundColor: colors.gold,
                width: 45,
                height: 3,
                borderRadius: 2,
              }}
            />
          </View>
          <View
            style={{
              padding: 20,
              gap: 18,
              width: "100%",
              maxWidth: 760,
              alignSelf: "center",
            }}
          >
            {children}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
export const Card = ({ children }: PropsWithChildren) => (
  <View style={styles.card}>{children}</View>
);
export const Body = ({ children }: PropsWithChildren) => (
  <Text style={styles.body}>{children}</Text>
);
export const Heading = ({ children }: PropsWithChildren) => (
  <Text accessibilityRole="header" style={styles.heading}>
    {children}
  </Text>
);
export function Notice({ message }: { message?: string | null }) {
  return message ? (
    <Text
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
      style={{ color: colors.danger, fontSize: 15, lineHeight: 23 }}
    >
      {message}
    </Text>
  ) : null;
}
export const Loading = () => (
  <ActivityIndicator accessibilityLabel="Loading" color={colors.green} />
);
export function Button({
  title,
  onPress,
  secondary = false,
  disabled = false,
}: {
  title: string;
  onPress: () => void;
  secondary?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => ({
        backgroundColor: secondary ? colors.soft : colors.green,
        opacity: disabled ? 0.5 : pressed ? 0.8 : 1,
        padding: 15,
        borderRadius: 12,
        minHeight: 50,
        justifyContent: "center",
      })}
    >
      <Text
        style={{
          fontSize: 16,
          fontWeight: "600",
          color: secondary ? colors.green : colors.paper,
          textAlign: "center",
        }}
      >
        {title}
      </Text>
    </Pressable>
  );
}
export function Action({
  title,
  run,
  secondary = false,
  disabled = false,
}: {
  title: string;
  run: () => Promise<unknown> | void;
  secondary?: boolean;
  disabled?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  const [error, setError] = useState("");
  return (
    <View style={{ gap: 8 }}>
      <Button
        title={busy ? "Please wait…" : title}
        disabled={busy || disabled}
        secondary={secondary}
        onPress={async () => {
          if (lock.current) return;
          lock.current = true;
          setBusy(true);
          setError("");
          try {
            await run();
          } catch (e) {
            setError(e instanceof Error ? e.message : "Please try again.");
          } finally {
            lock.current = false;
            setBusy(false);
          }
        }}
      />
      <Notice message={error} />
    </View>
  );
}
export function Field({ label, ...props }: TextInputProps & { label: string }) {
  return (
    <View style={{ gap: 7 }}>
      <Text style={{ color: colors.text, fontWeight: "500" }}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={colors.secondary}
        style={[
          styles.input,
          props.multiline ? { minHeight: 100, textAlignVertical: "top" } : null,
        ]}
        {...props}
      />
    </View>
  );
}
export function Toggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <View style={{ flexDirection: "row", gap: 12, alignItems: "center" }}>
      <Switch
        accessibilityLabel={label}
        value={value}
        onValueChange={onChange}
        trackColor={{ true: colors.muted }}
      />
      <Text style={[styles.body, { flex: 1 }]}>{label}</Text>
    </View>
  );
}
export const date = (value: string) =>
  new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
