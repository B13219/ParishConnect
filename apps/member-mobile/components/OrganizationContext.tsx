import type { ChurchTerminology, OrganizationPath } from "../types/api";
import { useSession } from "../providers/SessionProvider";
import { ancestryText, termView } from "../services/terminology";
import { Body } from "./ui";
export function OrganizationContext({ context, full = false }: {context?: {organization_path?: OrganizationPath; terminology?: ChurchTerminology}; full?: boolean}) {
  const {session} = useSession();
  const locale = session.user?.ui_language || "en";
  const text = ancestryText(context?.organization_path, locale, full);
  const label = termView(context?.terminology?.local_church, locale)?.label;
  return text || label ? <Body>{text || label}</Body> : null;
}
