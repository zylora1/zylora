export const AI_PROMPT_STORAGE_KEY = 'zylora.ai.prompt.v1';

export function storedAiPrompt(): string {
  if (typeof window === 'undefined') return '';
  return window.sessionStorage.getItem(AI_PROMPT_STORAGE_KEY)?.trim() ?? '';
}
