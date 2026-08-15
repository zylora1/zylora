'use client';

import { MotionConfig } from 'motion/react';
import type { ReactNode } from 'react';

import { motionTransitions } from '@/lib/motion-system';

export function MotionProvider({ children }: { children: ReactNode }) {
  return (
    <MotionConfig reducedMotion="user" transition={motionTransitions.slow}>
      {children}
    </MotionConfig>
  );
}
