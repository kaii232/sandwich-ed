import { cn } from "@/lib/cn";
export function Button({
  children,
  className,
  variant = "solid",
  disabled,
  ...props
}: any) {
  const base =
    "inline-flex items-center justify-center rounded-xl px-3 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-neutral-900 disabled:opacity-60";
  const styles =
    variant === "outline"
      ? "border bg-white hover:bg-neutral-50"
      : "bg-neutral-900 text-white hover:bg-neutral-800";
  return (
    <button
      className={cn(base, styles, className)}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
