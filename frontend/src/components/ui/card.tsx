import { cn } from "@/lib/cn";
export function Card({ className, ...props }: any) {
  return <div className={cn("border bg-white", className)} {...props} />;
}
export function CardHeader({ className, ...props }: any) {
  return <div className={cn("p-4 border-b", className)} {...props} />;
}
export function CardTitle({ className, ...props }: any) {
  return <h3 className={cn("text-lg font-semibold", className)} {...props} />;
}
export function CardContent({ className, ...props }: any) {
  return <div className={cn("p-4", className)} {...props} />;
}
