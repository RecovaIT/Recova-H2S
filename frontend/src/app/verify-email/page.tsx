"use client";
import { Suspense,useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
function Verify(){
 const token=useSearchParams().get("token")||"";const [message,setMessage]=useState("");const [busy,setBusy]=useState(false);
 async function confirm(){setBusy(true);try{const r=await api.post<{message:string}>("/auth/verify-email",{token});setMessage(r.message)}catch(e){setMessage(e instanceof Error?e.message:"Verification failed")}finally{setBusy(false)}}
 return <main className="flex min-h-screen items-center justify-center bg-slate-100 p-4"><section className="w-full max-w-md space-y-4 rounded-2xl bg-white p-6 shadow-sm"><h1 className="text-xl font-semibold">Verify your email</h1><p>Confirm this is your email address to complete your Recova account details.</p>{message?<p role="status">{message}</p>:<Button onClick={()=>void confirm()} disabled={busy||!token}>{busy?"Verifying…":"Verify email address"}</Button>}<Link className="block underline" href="/login">Return to sign in</Link></section></main>
}
export default function VerifyEmail(){return <Suspense fallback={<p>Loading verification…</p>}><Verify/></Suspense>}
