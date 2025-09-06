import { cn } from "@/lib/cn";
export function Input({ className, ...props }: any) {
  return (
    <input
      className={cn(
        "w-full rounded-xl border border-neutral-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neutral-900",
        className
      )}
      {...props}
    />
  );
}
