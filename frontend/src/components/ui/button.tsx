import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 font-medium transition-all duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-offset-1",
  {
    variants: {
      variant: {
        primary:
          "bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)] focus:ring-[var(--color-accent)]",
        secondary:
          "bg-[var(--color-surface-raised)] text-[var(--color-text-primary)] hover:bg-[var(--color-border)] focus:ring-[var(--color-border-strong)]",
        ghost:
          "bg-transparent text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-raised)] hover:text-[var(--color-text-primary)]",
        outline:
          "bg-transparent border border-[var(--color-border-strong)] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-raised)]",
        danger:
          "bg-[var(--color-danger)] text-white hover:opacity-90 focus:ring-[var(--color-danger)]",
      },
      size: {
        sm: "h-7 px-3 text-xs rounded-[var(--radius-sm)]",
        md: "h-9 px-4 text-sm rounded-[var(--radius-md)]",
        lg: "h-11 px-6 text-sm rounded-[var(--radius-md)]",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
);

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return (
    <button className={cn(buttonVariants({ variant, size }), className)} {...props} />
  );
}