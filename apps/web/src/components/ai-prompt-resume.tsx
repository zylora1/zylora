'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { storedAiPrompt } from '@/lib/ai-builder';

export function AiPromptResume() {
  const router = useRouter();

  useEffect(() => {
    if (storedAiPrompt()) router.replace('/app/ai-builder');
  }, [router]);

  return null;
}
