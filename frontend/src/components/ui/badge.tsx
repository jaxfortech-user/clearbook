import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 font-medium rounded-[var(--radius-pill)] px-2 py-0.5 text-xs",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--color-surface-raised)] text-[var(--color-text-secondary)]",
        success:
          "bg-[var(--color-success-soft)] text-[var(--color-success)]",
        warning:
          "bg-[var(--color-warning-soft)] text-[var(--color-warning)]",
        danger:
          "bg-[var(--color-danger-soft)] text-[var(--color-danger)]",
        accent:
          "bg-[var(--color-accent-soft)] text-[var(--color-accent)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}