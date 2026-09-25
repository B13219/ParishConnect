import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
export function useLoad<T>(
  key: string,
  loader: () => Promise<T>,
  enabled = true,
) {
  const ref = useRef(loader);
  useEffect(() => {
    ref.current = loader;
  }, [loader]);
  const [version, setVersion] = useState(0);
  const [result, setResult] = useState<{
    key: string;
    version: number;
    data?: T;
    error?: string;
    loading: boolean;
  }>({ key, version: 0, loading: enabled });
  useFocusEffect(
    useCallback(() => {
      let alive = true;
      if (enabled) {
        setResult({ key, version, loading: true });
        ref
          .current()
          .then((data) => {
            if (alive) setResult({ key, version, data, loading: false });
          })
          .catch((error) => {
            if (alive)
              setResult({
                key,
                version,
                error:
                  error instanceof Error
                    ? error.message
                    : "Unable to load. Please retry.",
                loading: false,
              });
          });
      }
      return () => {
        alive = false;
      };
    }, [key, version, enabled]),
  );
  const visible =
    result.key === key && result.version === version
      ? result
      : { key, version, loading: enabled };
  return { ...visible, refresh: () => setVersion((v) => v + 1) };
}
