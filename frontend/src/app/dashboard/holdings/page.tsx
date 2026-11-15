"use client";
import { HoldingsPanel } from "@/components/dashboard/HoldingsPanel";
import { usePersona } from "@/features/persona";

export default function HoldingsPage() {
  const { personaId } = usePersona();
  return <HoldingsPanel key={personaId} personaId={personaId} />;
}
