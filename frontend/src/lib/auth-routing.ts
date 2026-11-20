export function workspacePath(role: string | null | undefined): string {
  if (role === "patient") return "/portal";
  if (role === "supervisor") return "/worksafe";
  if (role === "authority_user") return "/authority";
  return "/dashboard";
}
