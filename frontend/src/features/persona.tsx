"use client";
import { createContext, useContext, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { PERSONAS, type Persona, type PersonaId } from "@/lib/personas";

type PersonaContext = { personaId: PersonaId; persona: Persona; setPersonaId: (id: PersonaId) => void };

const Context = createContext<PersonaContext | null>(null);

function personaFrom(value: string | null): PersonaId {
  return value === "mateo" || value === "robert" ? value : "amira";
}

/** The investor every page works on. Read once from `?persona=`, then held in state. */
export function PersonaProvider({ children }: { children: React.ReactNode }) {
  const params = useSearchParams();
  const [personaId, setPersonaId] = useState<PersonaId>(() => personaFrom(params.get("persona")));
  const value = useMemo<PersonaContext>(
    () => ({ personaId, persona: PERSONAS.find((p) => p.id === personaId)!, setPersonaId }),
    [personaId]
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function usePersona() {
  const value = useContext(Context);
  if (!value) throw new Error("usePersona must be used inside PersonaProvider");
  return value;
}
