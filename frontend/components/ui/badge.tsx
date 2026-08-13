import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border-2 border-[#1a1c1c] px-3 py-1 text-xs font-bold transition-colors",
  {
    variants: {
      variant: {
        default: "bg-[#ffd600] text-[#1a1c1c]",
        secondary: "bg-[#fcf3e0] text-[#1a1c1c]",
        outline: "bg-white text-[#1a1c1c]",
        success: "bg-[#00f5a0] text-[#002111]",
        warning: "bg-[#ffe170] text-[#1a1c1c]",
        destructive: "bg-red-50 text-red-700",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof badgeVariants>) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}
