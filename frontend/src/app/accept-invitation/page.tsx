"use client";
import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { authService } from "@/services/auth";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";

function Setup() {
  const token = useSearchParams().get("token") || "";
  const router = useRouter();
  const { session, refreshSession, logout } = useAuth();
  const [details,setDetails] = useState<{facility:string;email_masked:string;existing_account:boolean;used:boolean}|null>(null);
  const [name,setName]=useState("");const [password,setPassword]=useState("");const [repeat,setRepeat]=useState("");
  const [error,setError]=useState("");const [busy,setBusy]=useState(false);
  useEffect(()=>{
    let active=true;
    api.post<{facility:string;email_masked:string;existing_account:boolean;used:boolean}>("/auth/portal-invitations/inspect", {token})
      .then(d=>{if(active)setDetails(d)})
      .catch(e=>{if(active)setError(e instanceof Error?e.message:"Invitation unavailable")});
    return ()=>{active=false};
  },[token]);
  async function accept(e:React.FormEvent){
    e.preventDefault();setError("");setBusy(true);
    try {
      if (session) await authService.acceptPortalInvitation(token);
      else {
        if(password!==repeat)throw new Error("Passwords do not match");
        await authService.completePortalInvitation({token,new_password:password,full_name:name});
      }
      await refreshSession();router.replace("/portal");
    } catch(e){setError(e instanceof Error?e.message:"Could not complete setup")} finally{setBusy(false)}
  }
  const next=`/accept-invitation?token=${encodeURIComponent(token)}`;
  return <main className="flex min-h-screen items-center justify-center bg-slate-100 p-4"><Card className="w-full max-w-md">
    <CardHeader><CardTitle>Your Recova patient portal</CardTitle><CardDescription>{details?`${details.facility} invited ${details.email_masked}. Your care stays linked to this facility.`:"Checking your private invitation…"}</CardDescription></CardHeader>
    <CardContent className="space-y-4">
      {error&&<Alert variant="danger">{error} Ask your facility to resend the invitation if it expired.</Alert>}
      {details&&(session?<form onSubmit={accept} className="space-y-4"><p className="text-sm">Signed in as {session.user.email}</p><Button disabled={busy} type="submit">{busy?"Linking…":"Accept invitation and open portal"}</Button><Button type="button" variant="ghost" onClick={()=>void logout()}>Use a different account</Button></form>:
        details.existing_account?<><p className="text-sm">Use your existing password. Accepting this invitation will add this facility to your patient portal.</p><Link href={`/login?next=${encodeURIComponent(next)}`}><Button>Sign in to accept</Button></Link><Link className="block text-sm underline" href="/forgot-password">Forgot password?</Link></>:
        <form onSubmit={accept} className="space-y-4"><div><Label htmlFor="setup-name">Your full name</Label><Input id="setup-name" value={name} onChange={e=>setName(e.target.value)} required minLength={2} autoComplete="name"/></div><div><Label htmlFor="setup-password">Create your password</Label><Input id="setup-password" type="password" value={password} onChange={e=>setPassword(e.target.value)} required minLength={10} autoComplete="new-password"/><p className="mt-1 text-xs text-slate-500">At least 10 characters, including a letter and number.</p></div><div><Label htmlFor="setup-repeat">Confirm password</Label><Input id="setup-repeat" type="password" value={repeat} onChange={e=>setRepeat(e.target.value)} required autoComplete="new-password"/></div><Button className="w-full" disabled={busy} type="submit">{busy?"Setting up…":"Set up my portal"}</Button></form>)}
      <Link className="block text-sm underline" href="/login">Back to sign in</Link>
    </CardContent></Card></main>;
}
export default function AcceptInvitationPage(){return <Suspense fallback={<p className="p-6">Loading invitation…</p>}><Setup/></Suspense>}
