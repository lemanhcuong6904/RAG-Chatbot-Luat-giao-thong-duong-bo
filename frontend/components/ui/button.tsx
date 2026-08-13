import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-bold neo-border neo-interactive focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ring/35 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-[#ff6b00] text-white shadow-[4px_4px_0_#1a1c1c] hover:bg-[#ff7f25]",
        secondary: "bg-[#ffd600] text-[#1a1c1c] shadow-[4px_4px_0_#1a1c1c] hover:bg-[#ffe170]",
        outline: "bg-white text-[#1a1c1c] shadow-[3px_3px_0_#1a1c1c] hover:bg-[#ffd600]",
        ghost: "border-transparent bg-transparent shadow-none hover:border-[#1a1c1c] hover:bg-[#fcf3e0] hover:shadow-[3px_3px_0_#1a1c1c]",
        destructive: "bg-destructive text-destructive-foreground shadow-[4px_4px_0_#1a1c1c] hover:bg-red-700",
      },
      size: {
        default: "h-11 px-5 py-2",
        sm: "h-9 px-4",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
  ),
);
Button.displayName = "Button";
