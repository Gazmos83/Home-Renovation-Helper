import { ApiError } from "./api";

/** The API's refusal for one field, or `null` when it names another field. */
export function fieldError(error: unknown, field: string): string | null {
  return error instanceof ApiError && error.field === field ? error.message : null;
}

/** A refusal that names no field of this form, shown above it. */
export function formError(error: unknown, fields: string[]): string | null {
  if (!error) return null;
  if (error instanceof ApiError && error.field && fields.includes(error.field)) return null;
  return error instanceof Error ? error.message : "that did not work";
}

export function FieldError({ message }: { message: string | null }) {
  return message ? <p className="mt-1 text-sm text-destructive" role="alert">{message}</p> : null;
}
