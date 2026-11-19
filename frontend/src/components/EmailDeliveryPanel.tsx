"use client";
import {useCallback,useEffect,useState} from "react";
import {api} from "@/lib/api";
import {useAuth} from "@/hooks/useAuth";
import {Button} from "@/components/ui/button";
type Delivery={id:string;category:string;recipient:string;status:string;attempts:number;last_error?:string;sent_at?:string;expires_at?:string};
export function EmailDeliveryPanel(){
 const {hasPermission}=useAuth();const allowed=hasPermission("users:manage");
 const [rows,setRows]=useState<Delivery[]>([]),[message,setMessage]=useState("");
 const load=useCallback(async()=>{if(!allowed)return;try{setRows(await api.get<Delivery[]>("/settings/email-deliveries"));setMessage("")}catch(e){setMessage(e instanceof Error?e.message:"Cannot load email deliveries")}},[allowed]);
 useEffect(()=>{const timer=setTimeout(()=>void load(),0);const interval=setInterval(()=>void load(),15000);return()=>{clearTimeout(timer);clearInterval(interval)}},[load]);
 async function retry(id:string){try{await api.post(`/settings/email-deliveries/${id}/retry`);await load()}catch(e){setMessage(e instanceof Error?e.message:"Retry failed")}}
 if(!allowed)return null;
 return <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-5"><div className="flex items-center justify-between gap-4"><h2 className="font-semibold">Account email deliveries</h2><Button variant="outline" onClick={()=>void load()}>Refresh emails</Button></div><p className="text-xs text-slate-600">Identity email uses the server SMTP sender. Queued waits for the worker; sent means accepted by SMTP, not proof of inbox delivery. Expired links need a fresh invitation.</p>{message&&<p role="alert" className="text-sm text-red-700">{message}</p>}{!rows.length?<p className="text-sm text-slate-500">No account emails have been recorded for this facility.</p>:<div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr><th className="p-2">Purpose</th><th>Recipient</th><th>Status</th><th>Attempts</th><th>Next action</th></tr></thead><tbody>{rows.map(r=><tr key={r.id} className="border-t border-slate-100"><td className="p-2">{r.category}</td><td>{r.recipient}</td><td>{r.status}{r.last_error&&<p className="max-w-xs text-red-700">{r.last_error}</p>}</td><td>{r.attempts}</td><td>{["failed","not_configured"].includes(r.status)?<Button size="sm" variant="outline" onClick={()=>void retry(r.id)}>Retry email</Button>:r.status==="expired"?"Send a fresh invitation":"—"}</td></tr>)}</tbody></table></div>}</section>
}
