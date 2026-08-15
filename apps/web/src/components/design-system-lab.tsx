'use client';

import { Button, EmptyState, ErrorState, Notice, Skeleton, StatusBadge } from '@zylora/ui';
import { Check, ChevronDown, LoaderCircle, Sparkles } from 'lucide-react';
import { motion } from 'motion/react';

import styles from './design-system-lab.module.css';

const colors = [
  ['Canvas', '#080b12'],
  ['Surface', '#0c111a'],
  ['Raised', '#111722'],
  ['Brand', '#66e9b5'],
  ['Action', '#8c7dff'],
  ['Warning', '#f4bd67'],
  ['Danger', '#ff817d'],
] as const;

export function DesignSystemLab() {
  return (
    <main className={styles.lab}>
      <header className={styles.hero}>
        <p>Internal / development only</p>
        <h1>Zylora interface system.</h1>
        <span>
          Tokens, states, density, motion, and accessibility references in one living route.
        </span>
      </header>

      <section aria-labelledby="color-title">
        <h2 id="color-title">Color system</h2>
        <div className={styles.swatches}>
          {colors.map(([name, color]) => (
            <div key={name} style={{ '--swatch': color } as React.CSSProperties}>
              <i />
              <strong>{name}</strong>
              <code>{color}</code>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="type-title">
        <h2 id="type-title">Type and hierarchy</h2>
        <div className={styles.typeScale}>
          <p data-size="display">Build something worth arriving at.</p>
          <p data-size="title">One Website. Every useful decision.</p>
          <p data-size="heading">A confident starting point.</p>
          <p data-size="body">
            Clear product language is part of the interface—not decoration around it.
          </p>
          <p data-size="label">SECURE SESSION · SAVED 12 SECONDS AGO</p>
        </div>
      </section>

      <section aria-labelledby="controls-title">
        <h2 id="controls-title">Controls and system states</h2>
        <div className={styles.controlGrid}>
          <article>
            <h3>Actions</h3>
            <div className={styles.row}>
              <Button>Primary action</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="quiet">Quiet action</Button>
              <Button variant="danger">Delete</Button>
              <Button disabled>Working…</Button>
            </div>
          </article>
          <article>
            <h3>Fields</h3>
            <div className={styles.fields}>
              <label>
                Website name
                <input defaultValue="Northstar Advisory" />
              </label>
              <label>
                Page status
                <select defaultValue="active">
                  <option value="active">Active</option>
                  <option>Hidden</option>
                </select>
              </label>
              <label>
                URL slug
                <span>
                  <b>/services/</b>
                  <input defaultValue="strategy" />
                </span>
              </label>
              <label className={styles.check}>
                <input type="checkbox" defaultChecked /> Show in navigation
              </label>
            </div>
          </article>
          <article>
            <h3>Status and feedback</h3>
            <div className={styles.stack}>
              <div className={styles.row}>
                <StatusBadge tone="success">Published</StatusBadge>
                <StatusBadge tone="warning">Needs review</StatusBadge>
                <StatusBadge tone="danger">Failed</StatusBadge>
              </div>
              <Notice title="Draft saved" tone="success">
                Every manual and AI change is now part of revision 18.
              </Notice>
              <Notice title="Publishing check" tone="warning">
                This draft has 30 pages and requires Business to publish.
              </Notice>
            </div>
          </article>
          <article>
            <h3>Loading</h3>
            <div className={styles.stack}>
              <Skeleton className={styles.skeletonTitle} />
              <Skeleton />
              <Skeleton />
              <p className={styles.loading}>
                <LoaderCircle size={16} /> Preparing a secure preview…
              </p>
            </div>
          </article>
        </div>
      </section>

      <section aria-labelledby="motion-title">
        <h2 id="motion-title">Motion language</h2>
        <div className={styles.motionGrid}>
          {['Reveal', 'Layout', 'Feedback'].map((label, index) => (
            <motion.div
              key={label}
              whileHover={{ y: -6, scale: 1.015 }}
              transition={{ delay: index * 0.02 }}
            >
              <Sparkles size={18} />
              <strong>{label}</strong>
              <span>Purposeful, short, and reduced-motion aware.</span>
            </motion.div>
          ))}
        </div>
      </section>

      <section aria-labelledby="states-title">
        <h2 id="states-title">Route states</h2>
        <div className={styles.states}>
          <EmptyState
            eyebrow="No Websites yet"
            title="Choose a starting point"
            description="Every Zylora Website begins from an approved Template."
            action={
              <Button>
                <Check size={16} /> Browse Templates
              </Button>
            }
          />
          <ErrorState
            title="We could not load this Website"
            description="The request failed safely. Retry without losing the current draft."
            action={<Button variant="secondary">Try again</Button>}
          />
        </div>
      </section>

      <section className={styles.disclosure} aria-labelledby="disclosure-title">
        <h2 id="disclosure-title">Disclosure pattern</h2>
        <details>
          <summary>
            What belongs behind progressive disclosure?
            <ChevronDown aria-hidden="true" size={17} />
          </summary>
          <p>
            Advanced SEO, destructive actions, raw event detail, and infrequent settings remain
            available without competing with the current task.
          </p>
        </details>
      </section>
    </main>
  );
}
