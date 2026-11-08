import {
  useEffect,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import { AlertCircle, ArrowRight, Check, LoaderCircle, X } from "lucide-react";

export function Button({
  children,
  variant = "primary",
  loading = false,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  loading?: boolean;
}) {
  return (
    <button
      {...props}
      className={`button button-${variant} ${className}`}
      disabled={props.disabled || loading}
    >
      {loading && (
        <LoaderCircle size={16} className="spin" aria-hidden="true" />
      )}
      {children}
    </button>
  );
}

export function IconButton({
  label,
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      {...props}
      className={`icon-button ${className}`}
      aria-label={label}
      title={label}
    >
      {children}
    </button>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "green" | "amber";
}) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  wide = false,
}: {
  open: boolean;
  onClose(): void;
  title: string;
  description?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open]);
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    const cancel = (event: Event) => {
      event.preventDefault();
      onClose();
    };
    element.addEventListener("cancel", cancel);
    return () => element.removeEventListener("cancel", cancel);
  }, [onClose]);
  return (
    <dialog
      ref={dialog}
      className={`modal ${wide ? "modal-wide" : ""}`}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="modal-content">
        <div className="modal-header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description && <p id={descriptionId}>{description}</p>}
          </div>
          <IconButton label="Close dialog" onClick={onClose}>
            <X size={20} />
          </IconButton>
        </div>
        {children}
      </div>
    </dialog>
  );
}

export function EmptyState({
  icon,
  title,
  text,
  action,
  onAction,
}: {
  icon?: ReactNode;
  title: string;
  text: string;
  action?: string;
  onAction?(): void;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon ?? <span>◌</span>}</div>
      <h3>{title}</h3>
      <p>{text}</p>
      {action && (
        <Button variant="secondary" onClick={onAction}>
          {action}
          <ArrowRight size={16} />
        </Button>
      )}
    </div>
  );
}

export function ErrorNotice({
  message,
  retry,
}: {
  message: string;
  retry?(): void;
}) {
  return (
    <div className="notice notice-error" role="alert">
      <AlertCircle size={18} />
      <div>
        <p>{message}</p>
        {retry && (
          <button className="text-button" onClick={retry}>
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

export function Loading({
  label = "Loading your workspace",
}: {
  label?: string;
}) {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle size={24} className="spin" />
      <span>{label}</span>
    </div>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange(value: boolean): void;
  label: string;
  description?: string;
}) {
  const id = useId();
  return (
    <label className="toggle-row" htmlFor={id}>
      <span>
        <strong>{label}</strong>
        {description && <small>{description}</small>}
      </span>
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="toggle-track" aria-hidden="true">
        <span>
          <Check size={11} />
        </span>
      </span>
    </label>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export function PageHeading({
  eyebrow,
  title,
  text,
  action,
}: {
  eyebrow: string;
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="page-description">{text}</p>
      </div>
      {action}
    </header>
  );
}
