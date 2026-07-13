import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-teal-100 text-teal-800",
        green: "border-transparent bg-rag-greenBg text-emerald-800",
        amber: "border-transparent bg-rag-amberBg text-amber-800",
        red: "border-transparent bg-rag-redBg text-red-800",
        blue: "border-transparent bg-blue-50 text-blue-800",
        gray: "border-transparent bg-slate-100 text-slate-600",
        outline: "text-foreground border-border",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
