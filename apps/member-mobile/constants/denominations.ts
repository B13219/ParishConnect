export type DenominationOption = {
  value: string;
  label: string;
};

/**
 * Starter denomination catalogue for VINYRD church discovery.
 *
 * Keep values short and canonical because the backend currently performs an
 * exact, case-insensitive match on the church public-profile denomination.
 * Labels can carry Tanzania-specific organisation names without changing the
 * stored/filter value.
 *
 * Extend this list as new church bodies are onboarded; no schema change is
 * required.
 */
export const DENOMINATIONS: readonly DenominationOption[] = [
  { value: "Catholic", label: "Catholic (Roman Catholic)" },
  { value: "Lutheran", label: "Lutheran (ELCT / KKKT)" },
  { value: "Anglican", label: "Anglican (ACT / KAT)" },
  { value: "Moravian", label: "Moravian" },
  { value: "Africa Inland Church", label: "Africa Inland Church Tanzania (AICT)" },
  { value: "Baptist", label: "Baptist" },
  { value: "Mennonite", label: "Mennonite" },
  { value: "Presbyterian", label: "Presbyterian / Reformed" },
  { value: "Church of God", label: "Church of God" },
  { value: "Bible Church", label: "Bible Church" },
  { value: "Evangelistic", label: "Evangelistic Church" },
  { value: "Salvation Army", label: "Salvation Army" },
  { value: "Assemblies of God", label: "Assemblies of God (TAG)" },
  { value: "Seventh-day Adventist", label: "Seventh-day Adventist" },
  { value: "New Apostolic", label: "New Apostolic Church" },
  { value: "Pentecostal", label: "Pentecostal / Charismatic" },
  { value: "Orthodox", label: "Orthodox" },
  { value: "Methodist", label: "Methodist" },
  {
    value: "Non-denominational",
    label: "Non-denominational / Independent",
  },
] as const;
