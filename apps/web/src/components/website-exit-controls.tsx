'use client';

import { useState } from 'react';

import { apiRequest, csrfToken } from '@/lib/api';
import { formatMoney, type Money } from './commerce-types';
import styles from './commerce.module.css';

type TransferValidation = {
  website_id: string;
  recipient_email: string;
  eligible: boolean;
  requires_route_deactivation: boolean;
};

type Transfer = {
  status: 'VALIDATED' | 'DEACTIVATING' | 'COMPLETED' | 'FAILED';
};

type ExportPurchase = {
  id: string;
  status: string;
  price: Money;
};

type Checkout = {
  purchase: ExportPurchase;
  provider_available: boolean;
  detail: string;
};

function idempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export function WebsiteExitControls({ websiteId }: { websiteId: string }) {
  const [recipientEmail, setRecipientEmail] = useState('');
  const [validation, setValidation] = useState<TransferValidation | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [transfer, setTransfer] = useState<Transfer | null>(null);
  const [purchase, setPurchase] = useState<ExportPurchase | null>(null);
  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const headers = () => ({
    'X-CSRF-Token': csrfToken('zylora_user_csrf') ?? '',
  });

  async function validateRecipient() {
    setBusy(true);
    setError('');
    setTransfer(null);
    try {
      setValidation(
        await apiRequest<TransferValidation>(`/api/v1/websites/${websiteId}/transfers/validate`, {
          method: 'POST',
          headers: headers(),
          body: JSON.stringify({ recipient_email: recipientEmail }),
        }),
      );
    } catch (reason) {
      setValidation(null);
      setError(reason instanceof Error ? reason.message : 'Recipient validation failed.');
    } finally {
      setBusy(false);
    }
  }

  async function transferWebsite() {
    setBusy(true);
    setError('');
    try {
      setTransfer(
        await apiRequest<Transfer>(`/api/v1/websites/${websiteId}/transfers`, {
          method: 'POST',
          headers: { ...headers(), 'Idempotency-Key': idempotencyKey('website-transfer') },
          body: JSON.stringify({
            recipient_email: recipientEmail,
            confirmation_version: 'OWNER_TRANSFER_V1',
          }),
        }),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Website transfer failed.');
    } finally {
      setBusy(false);
    }
  }

  async function priceExport() {
    setBusy(true);
    setError('');
    setCheckout(null);
    try {
      setPurchase(
        await apiRequest<ExportPurchase>(`/api/v1/websites/${websiteId}/exports`, {
          method: 'POST',
          headers: { ...headers(), 'Idempotency-Key': idempotencyKey('website-export') },
          body: JSON.stringify({}),
        }),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Website ZIP export is unavailable.');
    } finally {
      setBusy(false);
    }
  }

  async function requestCheckout() {
    if (!purchase) return;
    setBusy(true);
    setError('');
    try {
      setCheckout(
        await apiRequest<Checkout>(`/api/v1/website-exports/${purchase.id}/checkout`, {
          method: 'POST',
          headers: headers(),
          body: JSON.stringify({}),
        }),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Secure checkout could not start.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.exitControls} aria-label="Transfer or export Website">
      <div>
        <h3>Transfer ownership</h3>
        <p>Transfers go only to an existing Zylora User. A live Website is taken offline first.</p>
      </div>
      <label>
        Recipient email
        <input
          aria-label="Transfer recipient email"
          type="email"
          value={recipientEmail}
          onChange={(event) => {
            setRecipientEmail(event.target.value);
            setValidation(null);
            setConfirmed(false);
          }}
        />
      </label>
      <div className={styles.publishRow}>
        <button
          className={styles.button}
          disabled={busy || !recipientEmail}
          onClick={validateRecipient}
          type="button"
        >
          Validate recipient
        </button>
        {validation ? (
          <span className={styles.success}>
            Eligible recipient
            {validation.requires_route_deactivation ? '; routing will be disabled first.' : '.'}
          </span>
        ) : null}
      </div>
      <label className={styles.confirmation}>
        <input
          checked={confirmed}
          disabled={!validation || busy}
          onChange={(event) => setConfirmed(event.target.checked)}
          type="checkbox"
        />
        I understand that the recipient becomes the only Website owner.
      </label>
      <div className={styles.publishRow}>
        <button
          className={styles.button}
          disabled={busy || !validation || !confirmed}
          onClick={transferWebsite}
          type="button"
        >
          Transfer Website
        </button>
        {transfer ? (
          <span className={styles.success}>
            {transfer.status === 'DEACTIVATING'
              ? 'Transfer is waiting for public routing to be disabled.'
              : `Transfer ${transfer.status.toLowerCase()}.`}
          </span>
        ) : null}
      </div>
      <div className={styles.exitDivider} />
      <div>
        <h3>Paid Website ZIP export</h3>
        <p>
          Pricing is chosen by the server from your billing region and snapshots this Website
          version.
        </p>
      </div>
      <div className={styles.publishRow}>
        <button className={styles.button} disabled={busy} onClick={priceExport} type="button">
          Price Website ZIP export
        </button>
        {purchase ? (
          <span className={styles.success}>{formatMoney(purchase.price)} snapshot ready.</span>
        ) : null}
      </div>
      {purchase ? (
        <div className={styles.publishRow}>
          <button className={styles.button} disabled={busy} onClick={requestCheckout} type="button">
            Proceed to secure checkout
          </button>
          {checkout && !checkout.provider_available ? (
            <span className={styles.error}>{checkout.detail}</span>
          ) : null}
        </div>
      ) : null}
      {error ? <p className={styles.error}>{error}</p> : null}
    </section>
  );
}
