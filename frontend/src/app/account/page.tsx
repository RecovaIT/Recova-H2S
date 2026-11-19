"use client";
import {AccountSecurityPanel} from "@/components/AccountSecurityPanel";
import {AuthGuard} from "@/components/AuthGuard";
import {AppShell} from "@/components/AppShell";
export default function AccountPage(){return <AuthGuard><AppShell title="Your account"><div className="max-w-lg"><AccountSecurityPanel/></div></AppShell></AuthGuard>}
