export const apiUrl = '';

export type Problem = {
  code?: string;
  detail?: string;
};

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = typeof FormData !== 'undefined' && init?.body instanceof FormData;
  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      ...(init?.body && !isFormData ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as Problem;
    throw new Error(problem.detail ?? 'We could not complete that request. Try again.');
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function csrfToken(cookieName: string): string | undefined {
  if (typeof document === 'undefined') return undefined;
  const prefix = `${cookieName}=`;
  return document.cookie
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix))
    ?.slice(prefix.length);
}
