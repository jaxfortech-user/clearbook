import { cn } from "@/lib/utils";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export function Input({ label, error, hint, className, id, ...props }: InputProps) {
  const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label
          htmlFor={inputId}
          className="text-xs font-medium text-[var(--color-text-secondary)]"
        >
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={cn(
          "h-9 w-full rounded-[var(--radius-md)] border px-3 text-sm bg-[var(--color-surface)] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] transition-colors duration-150",
          "focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)] focus:border-transparent",
          error
            ? "border-[var(--color-danger)]"
            : "border-[var(--color-border)] hover:border-[var(--color-border-strong)]",
          className
        )}
        {...props}
      />
      {error && (
        <p className="text-xs text-[var(--color-danger)]">{error}</p>
      )}
      {hint && !error && (
        <p className="text-xs text-[var(--color-text-muted)]">{hint}</p>
      )}
    </div>
  );
}