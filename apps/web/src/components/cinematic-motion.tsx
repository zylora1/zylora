'use client';

import Link from 'next/link';
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  type MotionStyle,
  type MotionValue,
} from 'motion/react';
import { createContext, type PointerEvent, type ReactNode, useContext, useRef } from 'react';

import styles from './cinematic-motion.module.css';

const SceneProgressContext = createContext<MotionValue<number> | null>(null);

type StickySceneProps = {
  children: ReactNode;
  className?: string | undefined;
  stageClassName?: string | undefined;
  id?: string | undefined;
  labelledBy?: string | undefined;
};

export function StickyScene({
  children,
  className,
  stageClassName,
  id,
  labelledBy,
}: StickySceneProps) {
  const target = useRef<HTMLElement>(null);
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({ target, offset: ['start start', 'end end'] });
  const progress = useSpring(scrollYProgress, {
    stiffness: 105,
    damping: 28,
    mass: 0.24,
    restDelta: 0.001,
  });

  return (
    <SceneProgressContext.Provider value={progress}>
      <section
        ref={target}
        {...(className ? { className } : {})}
        {...(id ? { id } : {})}
        {...(labelledBy ? { 'aria-labelledby': labelledBy } : {})}
        data-reduced-motion={reduceMotion ? 'true' : 'false'}
      >
        <div {...(stageClassName ? { className: stageClassName } : {})}>{children}</div>
      </section>
    </SceneProgressContext.Provider>
  );
}

type ScrollLayerProps = {
  children: ReactNode;
  className?: string | undefined;
  input?: number[] | undefined;
  x?: number[] | undefined;
  y?: number[] | undefined;
  scale?: number[] | undefined;
  rotate?: number[] | undefined;
  rotateX?: number[] | undefined;
  opacity?: number[] | undefined;
  perspective?: number | undefined;
  style?: MotionStyle | undefined;
};

export function ScrollLayer({
  children,
  className,
  input = [0, 1],
  x,
  y,
  scale,
  rotate,
  rotateX,
  opacity,
  perspective = 1200,
  style,
}: ScrollLayerProps) {
  const sceneProgress = useContext(SceneProgressContext);
  const fallback = useMotionValue(0);
  const progress = sceneProgress ?? fallback;
  const reduceMotion = useReducedMotion();
  const still = input.map(() => 0);
  const full = input.map(() => 1);
  const motionX = useTransform(progress, input, x ?? still);
  const motionY = useTransform(progress, input, y ?? still);
  const motionScale = useTransform(progress, input, scale ?? full);
  const motionRotate = useTransform(progress, input, rotate ?? still);
  const motionRotateX = useTransform(progress, input, rotateX ?? still);
  const motionOpacity = useTransform(progress, input, opacity ?? full);
  const resolvedStyle: MotionStyle = reduceMotion
    ? (style ?? {})
    : {
        ...style,
        x: motionX,
        y: motionY,
        scale: motionScale,
        rotate: motionRotate,
        rotateX: motionRotateX,
        opacity: motionOpacity,
        transformPerspective: perspective,
      };

  return (
    <motion.div {...(className ? { className } : {})} style={resolvedStyle}>
      {children}
    </motion.div>
  );
}

export function ViewportProgress() {
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 120, damping: 32, mass: 0.25 });
  if (reduceMotion) return null;
  return <motion.div className={styles.viewportProgress} style={{ scaleX }} aria-hidden="true" />;
}

export function MagneticLink({
  href,
  className,
  children,
}: {
  href: string;
  className?: string | undefined;
  children: ReactNode;
}) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 340, damping: 24, mass: 0.24 });
  const springY = useSpring(y, { stiffness: 340, damping: 24, mass: 0.24 });
  const reduceMotion = useReducedMotion();

  const move = (event: PointerEvent<HTMLSpanElement>) => {
    if (
      reduceMotion ||
      event.pointerType !== 'mouse' ||
      window.matchMedia('(pointer: coarse)').matches
    )
      return;
    const bounds = event.currentTarget.getBoundingClientRect();
    x.set((event.clientX - bounds.left - bounds.width / 2) * 0.14);
    y.set((event.clientY - bounds.top - bounds.height / 2) * 0.18);
  };

  const reset = () => {
    x.set(0);
    y.set(0);
  };

  const motionStyle: MotionStyle = reduceMotion ? {} : { x: springX, y: springY };

  return (
    <motion.span
      className={styles.magnetic}
      style={motionStyle}
      onPointerMove={move}
      onPointerLeave={reset}
    >
      <Link href={href} {...(className ? { className } : {})}>
        {children}
      </Link>
    </motion.span>
  );
}

export function SpotlightArticle({
  children,
  className,
}: {
  children: ReactNode;
  className?: string | undefined;
}) {
  const article = useRef<HTMLElement>(null);
  const reduceMotion = useReducedMotion();

  const track = (event: PointerEvent<HTMLElement>) => {
    if (reduceMotion || event.pointerType !== 'mouse') return;
    const bounds = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty('--spotlight-x', `${event.clientX - bounds.left}px`);
    event.currentTarget.style.setProperty('--spotlight-y', `${event.clientY - bounds.top}px`);
  };

  return (
    <article
      ref={article}
      className={`${styles.spotlight} ${className ?? ''}`}
      onPointerMove={track}
    >
      {children}
    </article>
  );
}
