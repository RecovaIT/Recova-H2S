import { NextResponse } from 'next/server';
export async function POST() {
  return NextResponse.json({ message: 'pipeline route scaffold — implemented in PR #4' });
}