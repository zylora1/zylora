'use client';

import type { TemplateDocument } from '@zylora/template-schema';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import { apiRequest } from '@/lib/api';
import { sandboxDocument } from '@/lib/template-sandbox';
import styles from './template-platform.module.css';

const devices = { desktop: '100%', tablet: '768px', mobile: '390px' } as const;

export function TemplatePreview({
  slug,
  version,
  name,
}: {
  slug: string;
  version: number;
  name: string;
}) {
  const [device, setDevice] = useState<keyof typeof devices>('desktop');
  const [source, setSource] = useState('');
  const [displayName, setDisplayName] = useState(name);
  const [error, setError] = useState('');
  useEffect(() => {
    apiRequest<{ document: TemplateDocument }>(
      `/api/v1/templates/${slug}/versions/${version}/preview`,
    )
      .then((value) => {
        setDisplayName(value.document.metadata.name);
        setSource(sandboxDocument(value.document));
      })
      .catch((reason) =>
        setError(reason instanceof Error ? reason.message : 'Preview unavailable.'),
      );
  }, [slug, version]);
  return (
    <main className={styles.previewPage}>
      <div className={styles.previewToolbar}>
        <Link href={`/templates/${slug}`}>← Details</Link>
        <strong>{displayName}</strong>
        {Object.keys(devices).map((value) => (
          <button
            type="button"
            key={value}
            data-active={device === value}
            onClick={() => setDevice(value as keyof typeof devices)}
          >
            {value}
          </button>
        ))}
      </div>
      <div className={styles.previewStage}>
        {error ? (
          <p role="alert">{error}</p>
        ) : source ? (
          <iframe
            title={`${displayName} responsive preview`}
            className={styles.previewFrame}
            style={{ width: devices[device] }}
            sandbox=""
            referrerPolicy="no-referrer"
            srcDoc={source}
          />
        ) : (
          <p>Preparing secure preview…</p>
        )}
      </div>
    </main>
  );
}
