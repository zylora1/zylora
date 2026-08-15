'use client';

import { ArrowUpRight, Sparkles } from 'lucide-react';
import { useReducedMotion } from 'motion/react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { type FormEvent, useEffect, useState } from 'react';

import { AI_PROMPT_STORAGE_KEY } from '@/lib/ai-builder';
import styles from './landing-page.module.css';

const examples = [
  'A premium dental clinic website with online enquiries…',
  'A calm architecture portfolio for a residential studio…',
  'A conversion-focused website for my coaching academy…',
  'A credible launch website for a B2B software startup…',
] as const;

export function LandingPrompt() {
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const [value, setValue] = useState('');
  const [example, setExample] = useState(0);

  useEffect(() => {
    if (value || reduceMotion) return;
    const timer = window.setInterval(
      () => setExample((current) => (current + 1) % examples.length),
      3400,
    );
    return () => window.clearInterval(timer);
  }, [reduceMotion, value]);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const prompt = value.trim();
    if (!prompt) return;
    window.sessionStorage.setItem(AI_PROMPT_STORAGE_KEY, prompt);
    router.push('/signup?intent=ai');
  };

  return (
    <div className={styles.promptCluster}>
      <form className={styles.promptForm} onSubmit={submit}>
        <label className={styles.srOnly} htmlFor="landing-ai-prompt">
          Describe the website you want to build
        </label>
        <Sparkles aria-hidden="true" size={18} />
        <textarea
          id="landing-ai-prompt"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={examples[example]}
          rows={2}
          maxLength={2000}
          required
        />
        <button type="submit" aria-label="Build this website with AI">
          <span>Build with AI</span>
          <ArrowUpRight aria-hidden="true" size={17} />
        </button>
      </form>
      <div className={styles.promptFoot}>
        <span>Describe the outcome. Zylora plans the pages, design, and search foundations.</span>
        <Link href="/templates">Browse Templates</Link>
      </div>
    </div>
  );
}
