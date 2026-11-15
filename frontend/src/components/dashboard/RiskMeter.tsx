export function RiskMeter({ level, size = "sm" }: { level: number; size?: "sm" | "lg" }) {
  const h = size === "lg" ? "h-2.5" : "h-1.5";
  return (
    <div className="flex gap-1" aria-label={`Risk level ${level} of 3`}>
      {[1, 2, 3].map((i) => (
        <span key={i} className={`${h} flex-1 rounded-full ${i <= level ? "bg-brand-500" : "bg-brand-100"}`} />
      ))}
    </div>
  );
}
