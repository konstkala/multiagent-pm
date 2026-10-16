import { redirect } from "next/navigation";

// Signed-out visitors are sent on to /sign-in by src/proxy.ts.
export default function Home() {
  redirect("/projects");
}
