import { ancestryText, termView } from "../services/terminology";
import type { OrganizationPath } from "../types/api";
const path: OrganizationPath = [
  {level_key: "district", name: "Jimbo la Dar es Salaam", presentation: {
    en: {label: "District", bilingual_label: "District / Jimbo", name: "Dar es Salaam District"},
    sw: {label: "Jimbo", bilingual_label: "Jimbo / District", name: "Jimbo la Dar es Salaam"},
  }},
  {level_key: "local_church", name: "TAG Mikocheni"},
];
test("English and Kiswahili use server terminology and official names", () => {
  expect(ancestryText(path, "en")).toBe("Dar es Salaam District — District");
  expect(ancestryText(path, "sw")).toBe("Jimbo la Dar es Salaam — Jimbo");
  expect(ancestryText(path, "sw", true)).toContain("TAG Mikocheni");
});
test("offline old payload and missing language have a safe fallback", () => {
  expect(ancestryText(undefined, "sw")).toBe("");
  expect(termView({en:{label:"Parish", bilingual_label:"Parish"}}, "sw")?.label).toBe("Parish");
  expect(ancestryText([{level_key:"parish", name:"St Mary", labels:{en:"Parish"}}], "sw", true)).toBe("St Mary — Parish");
});
