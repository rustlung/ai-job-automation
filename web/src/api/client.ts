import type { ApiErrorBody } from "../types/api";

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
export const API_BASE_URL = rawBaseUrl.replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly errorCode?: string
  ) {
    super(message);
  }
}

function errorDetails(body: ApiErrorBody): { message: string; errorCode?: string } {
  if (typeof body.detail === "string") return { message: body.detail };
  if (body.detail?.error_code) return { message: "Запрос не выполнен", errorCode: body.detail.error_code };
  return { message: "Запрос не выполнен" };
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers }
    });
  } catch {
    throw new ApiError("Не удалось подключиться к Orchestrator", 0);
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    const details = errorDetails(body);
    throw new ApiError(details.message, response.status, details.errorCode);
  }
  return response.json() as Promise<T>;
}
