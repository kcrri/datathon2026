export function PillButton({
  icon,
  children,
  onClick,
}: {
  icon: string;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex h-11 w-full items-center gap-3 rounded-full border border-slate-700 bg-white px-4 text-sm font-medium transition hover:bg-slate-50"
    >
      <span className="flex h-5 w-5 items-center justify-center rounded-full border border-slate-700 text-xs leading-none">
        {icon}
      </span>
      {children}
    </button>
  );
}
