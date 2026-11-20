import { redirect } from "next/navigation";

export default async function LegacyRegistrationPage({
  searchParams,
}: {
  searchParams: Promise<{ programme?: string | string[] }>;
}) {
  const { programme } = await searchParams;
  const selected =
    typeof programme === "string" &&
    ["core", "loop", "neuro", "worksafe"].includes(programme)
      ? `?programme=${programme}`
      : "";
  redirect(`/signup${selected}`);
}
