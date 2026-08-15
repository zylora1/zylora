import type { CSSProperties } from 'react';

import type { TemplateSummary } from './template-gallery';
import styles from './template-platform.module.css';

const palettes = [
  ['#173f36', '#7df9c5', '#f0eadf'],
  ['#243e70', '#b9c9ff', '#eff3fb'],
  ['#6f3b2a', '#ffbf7d', '#f8eee3'],
  ['#443266', '#dcb7ff', '#f1eefa'],
  ['#202724', '#dcec74', '#eff2e6'],
  ['#7a3153', '#ffc3d7', '#faedf2'],
  ['#174c5a', '#8de2d3', '#e9f3f2'],
  ['#5e3b26', '#f2bd69', '#f7efe6'],
  ['#262f4b', '#9db7ff', '#edf0f8'],
  ['#354635', '#c2e39a', '#edf3e9'],
] as const;

export function TemplateCardPreview({ item, index }: { item: TemplateSummary; index: number }) {
  const [primary, accent, surface] = palettes[index % palettes.length] ?? palettes[0];
  const family =
    item.tags.find((tag) => tag.startsWith('family-'))?.replace('family-', '') ?? 'studio';
  return (
    <div
      className={styles.cardPreview}
      data-family={family}
      style={
        {
          '--card-primary': primary,
          '--card-accent': accent,
          '--card-surface': surface,
        } as CSSProperties
      }
    >
      <div className={styles.cardBrowser}>
        <i />
        <i />
        <i />
        <small>zylora.site</small>
      </div>
      <div className={styles.cardSite}>
        <div className={styles.cardSiteNav}>
          <b>{item.name.split(' ')[0]}</b>
          <span>About&nbsp;&nbsp; Work&nbsp;&nbsp; Contact</span>
        </div>
        <div className={styles.cardHero}>
          <small>{item.category}</small>
          <strong>{item.name}</strong>
          <em>Explore the story →</em>
        </div>
        <div className={styles.cardMiniGrid}>
          <i />
          <i />
          <i />
        </div>
      </div>
    </div>
  );
}
