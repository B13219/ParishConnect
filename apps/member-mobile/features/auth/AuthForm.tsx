import { useState } from "react";
import { router } from "expo-router";
import { Action, Body, Button, Field, Screen } from "../../components/ui";
import { useSession } from "../../providers/SessionProvider";
export default function AuthForm({ register = false }: { register?: boolean }) {
  const { controller } = useSession();
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  return (
    <Screen
      title={register ? "Create your account" : "Welcome back"}
      subtitle={
        register
          ? "One VINYRD account, wherever you worship."
          : "Sign in to your VINYRD community."
      }
    >
      {register ? (
        <>
          <Field
            label="First name"
            value={first}
            onChangeText={setFirst}
            autoComplete="given-name"
            maxLength={80}
          />
          <Field
            label="Last name"
            value={last}
            onChangeText={setLast}
            autoComplete="family-name"
            maxLength={79}
          />
        </>
      ) : null}
      <Field
        label="Email"
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
        autoComplete="email"
        maxLength={255}
      />
      <Field
        label="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        autoCapitalize="none"
        autoComplete={register ? "new-password" : "current-password"}
        maxLength={256}
      />
      {register ? (
        <Body>
          Use at least 12 characters. Creating an account does not automatically
          join a church.
        </Body>
      ) : null}
      <Action
        title={register ? "Create VINYRD account" : "Sign in"}
        run={async () => {
          if (
            !email.trim() ||
            !password ||
            (register &&
              (!first.trim() || !last.trim() || password.length < 12))
          )
            throw new Error(
              "Complete all fields" +
                (register
                  ? " and use a password of at least 12 characters."
                  : "."),
            );
          await controller.authenticate(
            register ? "register" : "login",
            register
              ? {
                  first_name: first.trim(),
                  last_name: last.trim(),
                  email: email.trim(),
                  password,
                }
              : { email: email.trim(), password },
          );
        }}
      />
      <Button
        secondary
        title={
          register
            ? "Already have an account? Sign in"
            : "New to VINYRD? Create account"
        }
        onPress={() => router.replace(register ? "/login" : "/register")}
      />
      {!register ? (
        <Body>
          For password recovery, contact VINYRD support. Recovery delivery is
          not enabled by this app.
        </Body>
      ) : null}
    </Screen>
  );
}
