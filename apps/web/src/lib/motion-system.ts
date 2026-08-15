import type { Transition, Variants } from 'motion/react';

export const motionDurations = {
  fast: 0.15,
  normal: 0.24,
  slow: 0.52,
  cinematic: 0.8,
} as const;

export const motionEasings = {
  immediate: [0.2, 0, 0, 1],
  standard: [0.22, 1, 0.36, 1],
  exit: [0.4, 0, 1, 1],
} as const;

export const motionTransitions = {
  fast: { duration: motionDurations.fast, ease: motionEasings.immediate },
  normal: { duration: motionDurations.normal, ease: motionEasings.standard },
  slow: { duration: motionDurations.slow, ease: motionEasings.standard },
  cinematic: { duration: motionDurations.cinematic, ease: motionEasings.standard },
} satisfies Record<string, Transition>;

export const motionVariants = {
  fade: {
    hidden: { opacity: 0 },
    visible: { opacity: 1 },
    exit: { opacity: 0 },
  },
  fadeUp: {
    hidden: { opacity: 0, y: 26 },
    visible: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -10 },
  },
  scale: {
    hidden: { opacity: 0, scale: 0.97 },
    visible: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.985 },
  },
  blurIn: {
    hidden: { opacity: 0, filter: 'blur(10px)' },
    visible: { opacity: 1, filter: 'blur(0px)' },
    exit: { opacity: 0, filter: 'blur(5px)' },
  },
  stagger: {
    hidden: {},
    visible: { transition: { staggerChildren: 0.055 } },
  },
} satisfies Record<string, Variants>;

export function withDelay(transition: Transition, order: number): Transition {
  return { ...transition, delay: order * 0.055 };
}
