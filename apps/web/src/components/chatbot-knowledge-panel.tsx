'use client';

import {
  Bot,
  CheckCircle2,
  FileText,
  LoaderCircle,
  MessageCircle,
  RefreshCw,
  Send,
  ShieldCheck,
  Trash2,
  UploadCloud,
} from 'lucide-react';
import {
  type DragEvent,
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Notice, StatusBadge } from '@zylora/ui';

import { apiRequest, csrfToken } from '@/lib/api';
import styles from './chatbot-knowledge-panel.module.css';

type Source = {
  id: string;
  type: string;
  display_name: string;
  mime_type: string;
  byte_size: number;
  status: string;
  failure_code: string | null;
  failure_message: string | null;
  indexed_at: string | null;
  created_at: string;
  updated_at: string;
};

type Overview = {
  chatbot_status: string;
  chatbot_enabled: boolean;
  active_index_id: string | null;
  knowledge_generation: number | null;
  last_indexed_at: string | null;
  source_count: number;
  source_limit: number;
  sources: Source[];
};

type WhatsAppSetting = {
  configured: boolean;
  enabled: boolean;
  status: string;
  masked_number: string | null;
  country_code: string | null;
  consented_at: string | null;
  last_tested_at: string | null;
};

type Preview = { answer: string; sources: string[] };

const ACTIVE_SOURCE_STATES = new Set(['UPLOADED', 'SCANNING', 'PROCESSING']);
const ACCEPT = '.pdf,.docx,.txt,.md';

function mutationHeaders(): HeadersInit {
  const token = csrfToken('zylora_user_csrf');
  return token ? { 'X-CSRF-Token': token } : {};
}

function humanBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function relativeTime(value: string | null) {
  if (!value) return 'Not indexed yet';
  const minutes = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 60_000));
  if (minutes < 1) return 'Updated just now';
  if (minutes === 1) return 'Updated 1 minute ago';
  if (minutes < 60) return `Updated ${minutes} minutes ago`;
  return `Updated ${Math.round(minutes / 60)} hours ago`;
}

function sourceStatus(value: string) {
  return (
    {
      UPLOADED: 'Uploading',
      SCANNING: 'Scanning',
      PROCESSING: 'Building knowledge',
      READY: 'Ready',
      FAILED: 'Failed',
    }[value] ?? value
  );
}

export function ChatbotKnowledgePanel({ websiteId }: { websiteId: string }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [whatsapp, setWhatsapp] = useState<WhatsAppSetting | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [notice, setNotice] = useState<{ tone: 'danger' | 'success'; text: string } | null>(null);
  const [previewQuestion, setPreviewQuestion] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [phone, setPhone] = useState('');
  const [country, setCountry] = useState('IN');
  const [whatsappEnabled, setWhatsappEnabled] = useState(false);
  const [consent, setConsent] = useState(false);

  const refresh = useCallback(
    async (quiet = false) => {
      if (!quiet) setLoading(true);
      try {
        const [knowledgeResult, whatsappResult] = await Promise.all([
          apiRequest<Overview>(`/api/v1/websites/${websiteId}/knowledge`),
          apiRequest<WhatsAppSetting>(`/api/v1/websites/${websiteId}/whatsapp-notifications`),
        ]);
        setOverview(knowledgeResult);
        setWhatsapp(whatsappResult);
        setWhatsappEnabled(whatsappResult.enabled);
        setCountry(whatsappResult.country_code ?? 'IN');
      } catch (error) {
        if (!quiet) {
          setNotice({
            tone: 'danger',
            text: error instanceof Error ? error.message : 'Could not load chatbot settings.',
          });
        }
      } finally {
        if (!quiet) setLoading(false);
      }
    },
    [websiteId],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => void refresh(), 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  const hasActiveWork = useMemo(
    () =>
      overview?.chatbot_status === 'INDEXING' ||
      overview?.sources.some((source) => ACTIVE_SOURCE_STATES.has(source.status)),
    [overview],
  );

  useEffect(() => {
    if (!hasActiveWork) return;
    const timer = window.setInterval(() => void refresh(true), 5000);
    return () => window.clearInterval(timer);
  }, [hasActiveWork, refresh]);

  async function upload(files: FileList | File[]) {
    const selected = Array.from(files);
    if (!selected.length) return;
    setBusy('upload');
    setNotice(null);
    try {
      await Promise.all(
        selected.map((file) => {
          const body = new FormData();
          body.append('file', file);
          return apiRequest<Source>(`/api/v1/websites/${websiteId}/knowledge`, {
            method: 'POST',
            headers: mutationHeaders(),
            body,
          });
        }),
      );
      setNotice({
        tone: 'success',
        text:
          selected.length === 1
            ? 'Document uploaded. Building knowledge now.'
            : 'Documents uploaded. Building knowledge now.',
      });
      await refresh(true);
    } catch (error) {
      setNotice({
        tone: 'danger',
        text: error instanceof Error ? error.message : 'Document could not be uploaded.',
      });
    } finally {
      setBusy(null);
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    void upload(event.dataTransfer.files);
  }

  function onUploadKeyDown(event: KeyboardEvent<HTMLLabelElement>) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      inputRef.current?.click();
    }
  }

  async function sourceAction(source: Source, action: 'retry' | 'delete') {
    setBusy(source.id);
    setNotice(null);
    try {
      await apiRequest<void | Source>(
        `/api/v1/websites/${websiteId}/knowledge/${source.id}${action === 'retry' ? '/retry' : ''}`,
        {
          method: action === 'retry' ? 'POST' : 'DELETE',
          headers: mutationHeaders(),
          body: JSON.stringify({}),
        },
      );
      await refresh(true);
    } catch (error) {
      setNotice({
        tone: 'danger',
        text: error instanceof Error ? error.message : 'Could not update this knowledge source.',
      });
    } finally {
      setBusy(null);
    }
  }

  async function toggleChatbot() {
    if (!overview) return;
    setBusy('chatbot');
    try {
      const result = await apiRequest<Overview>(`/api/v1/websites/${websiteId}/chatbot`, {
        method: 'PATCH',
        headers: mutationHeaders(),
        body: JSON.stringify({ enabled: !overview.chatbot_enabled }),
      });
      setOverview(result);
    } catch (error) {
      setNotice({
        tone: 'danger',
        text: error instanceof Error ? error.message : 'Could not update the chatbot.',
      });
    } finally {
      setBusy(null);
    }
  }

  async function testChatbot(event: FormEvent) {
    event.preventDefault();
    if (!previewQuestion.trim()) return;
    setBusy('preview');
    setPreview(null);
    try {
      setPreview(
        await apiRequest<Preview>(`/api/v1/websites/${websiteId}/chatbot/preview`, {
          method: 'POST',
          headers: mutationHeaders(),
          body: JSON.stringify({ message: previewQuestion }),
        }),
      );
    } catch (error) {
      setNotice({
        tone: 'danger',
        text: error instanceof Error ? error.message : 'The chatbot preview is unavailable.',
      });
    } finally {
      setBusy(null);
    }
  }

  async function saveWhatsApp(event: FormEvent) {
    event.preventDefault();
    setBusy('whatsapp');
    try {
      const result = await apiRequest<WhatsAppSetting>(
        `/api/v1/websites/${websiteId}/whatsapp-notifications`,
        {
          method: 'PATCH',
          headers: mutationHeaders(),
          body: JSON.stringify({
            phone_number: phone || null,
            country_code: country,
            enabled: whatsappEnabled,
            consent,
          }),
        },
      );
      setWhatsapp(result);
      setNotice({ tone: 'success', text: 'WhatsApp notification settings saved.' });
    } catch (error) {
      setNotice({
        tone: 'danger',
        text: error instanceof Error ? error.message : 'Could not save WhatsApp settings.',
      });
    } finally {
      setBusy(null);
    }
  }

  async function sendWhatsAppTest() {
    setBusy('whatsapp-test');
    try {
      await apiRequest(`/api/v1/websites/${websiteId}/whatsapp-notifications/test`, {
        method: 'POST',
        headers: mutationHeaders(),
        body: JSON.stringify({}),
      });
      setNotice({
        tone: 'success',
        text: 'Test notification queued. Delivery status will update shortly.',
      });
      await refresh(true);
    } catch (error) {
      setNotice({
        tone: 'danger',
        text: error instanceof Error ? error.message : 'Could not send the test notification.',
      });
    } finally {
      setBusy(null);
    }
  }

  if (loading) {
    return (
      <div className={styles.skeleton} aria-label="Loading chatbot and knowledge settings">
        <span />
        <span />
        <span />
      </div>
    );
  }

  if (!overview) {
    return (
      <Notice tone="danger" title="Could not load settings">
        Chatbot settings could not be loaded.
      </Notice>
    );
  }

  return (
    <div className={styles.root}>
      <div className={styles.heading}>
        <div>
          <p className={styles.eyebrow}>Customer intelligence</p>
          <h1>Chatbot &amp; Knowledge</h1>
          <p>Teach your website to answer real customer questions, then turn intent into leads.</p>
        </div>
        <StatusBadge tone={overview.chatbot_enabled ? 'success' : 'neutral'}>
          {overview.chatbot_status === 'INDEXING'
            ? 'Indexing'
            : overview.chatbot_enabled
              ? 'Active'
              : 'Disabled'}
        </StatusBadge>
      </div>

      {notice ? (
        <div aria-live="polite">
          <Notice tone={notice.tone} title={notice.tone === 'danger' ? 'Action needed' : 'Saved'}>
            {notice.text}
          </Notice>
        </div>
      ) : null}

      <section className={styles.heroCard} aria-labelledby="ai-chatbot-title">
        <div className={styles.iconTile}>
          <Bot aria-hidden size={24} />
        </div>
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}>AI Chatbot</p>
          <h2 id="ai-chatbot-title">Answers grounded in your business</h2>
          <p>
            {overview.source_count} {overview.source_count === 1 ? 'source' : 'sources'} {' / '}
            {relativeTime(overview.last_indexed_at)}
          </p>
        </div>
        <button
          className={styles.secondary}
          disabled={busy === 'chatbot'}
          onClick={() => void toggleChatbot()}
          type="button"
        >
          {busy === 'chatbot' ? <LoaderCircle className={styles.spin} size={16} /> : null}
          {overview.chatbot_enabled ? 'Disable chatbot' : 'Enable chatbot'}
        </button>
      </section>

      <div className={styles.columns}>
        <section className={styles.panel} aria-labelledby="knowledge-title">
          <div className={styles.panelHeading}>
            <div>
              <p className={styles.eyebrow}>Knowledge Sources</p>
              <h2 id="knowledge-title">Give every answer context</h2>
            </div>
            <span>
              {overview.source_count}/{overview.source_limit}
            </span>
          </div>
          <p>Upload documents your AI chatbot can use to answer questions about your business.</p>

          <label
            className={`${styles.dropzone} ${dragging ? styles.dragging : ''}`}
            onDragEnter={() => setDragging(true)}
            onDragLeave={() => setDragging(false)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={onDrop}
            onKeyDown={onUploadKeyDown}
            tabIndex={0}
          >
            {busy === 'upload' ? (
              <LoaderCircle className={styles.spin} aria-hidden size={28} />
            ) : (
              <UploadCloud aria-hidden size={28} />
            )}
            <strong>
              {busy === 'upload' ? 'Uploading documents' : 'Drop PDFs or documents here'}
            </strong>
            <span>PDF, DOCX, TXT or Markdown / Choose files</span>
            <input
              ref={inputRef}
              accept={ACCEPT}
              disabled={busy === 'upload'}
              multiple
              onChange={(event) => event.target.files && void upload(event.target.files)}
              type="file"
            />
          </label>

          <div className={styles.sourceList} aria-live="polite">
            {overview.sources.length ? (
              overview.sources.map((source) => (
                <article className={styles.source} key={source.id}>
                  <div className={styles.fileIcon}>
                    <FileText aria-hidden size={18} />
                  </div>
                  <div className={styles.sourceCopy}>
                    <strong title={source.display_name}>{source.display_name}</strong>
                    <span>
                      {source.type} / {humanBytes(source.byte_size)}
                    </span>
                    {source.failure_message ? <small>{source.failure_message}</small> : null}
                  </div>
                  <StatusBadge
                    tone={
                      source.status === 'READY'
                        ? 'success'
                        : source.status === 'FAILED'
                          ? 'danger'
                          : 'neutral'
                    }
                  >
                    {sourceStatus(source.status)}
                  </StatusBadge>
                  <div className={styles.rowActions}>
                    {source.status === 'FAILED' ? (
                      <button
                        aria-label={`Retry ${source.display_name}`}
                        disabled={busy === source.id}
                        onClick={() => void sourceAction(source, 'retry')}
                        type="button"
                      >
                        <RefreshCw size={15} />
                      </button>
                    ) : null}
                    <button
                      aria-label={`Delete ${source.display_name}`}
                      disabled={busy === source.id}
                      onClick={() => void sourceAction(source, 'delete')}
                      type="button"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </article>
              ))
            ) : (
              <div className={styles.empty}>
                <ShieldCheck aria-hidden size={22} />
                <p>Your files stay private and are used only by this website&apos;s chatbot.</p>
              </div>
            )}
          </div>
        </section>

        <div className={styles.stack}>
          <section className={styles.panel} aria-labelledby="preview-title">
            <div className={styles.panelHeading}>
              <div>
                <p className={styles.eyebrow}>Test chatbot</p>
                <h2 id="preview-title">Ask before visitors do</h2>
              </div>
              <MessageCircle aria-hidden size={20} />
            </div>
            <form className={styles.previewForm} onSubmit={testChatbot}>
              <label htmlFor="chatbot-preview-question">
                Try pricing, opening hours or a policy
              </label>
              <div>
                <input
                  id="chatbot-preview-question"
                  onChange={(event) => setPreviewQuestion(event.target.value)}
                  placeholder="How much does the course cost?"
                  value={previewQuestion}
                />
                <button disabled={busy === 'preview' || !previewQuestion.trim()} type="submit">
                  {busy === 'preview' ? (
                    <LoaderCircle className={styles.spin} size={16} />
                  ) : (
                    <Send size={16} />
                  )}
                  Ask
                </button>
              </div>
            </form>
            {preview ? (
              <div className={styles.answer} aria-live="polite">
                <span>
                  <Bot aria-hidden size={16} /> Zylora AI
                </span>
                <p>{preview.answer}</p>
                {preview.sources.length ? (
                  <small>Sources: {preview.sources.join(', ')}</small>
                ) : null}
              </div>
            ) : null}
          </section>

          <section className={styles.panel} aria-labelledby="whatsapp-title">
            <div className={styles.panelHeading}>
              <div>
                <p className={styles.eyebrow}>Lead notifications</p>
                <h2 id="whatsapp-title">WhatsApp</h2>
              </div>
              {whatsapp?.enabled ? <CheckCircle2 color="var(--z-color-success)" size={20} /> : null}
            </div>
            <p>Get a WhatsApp notification whenever your website receives a new lead.</p>
            <form className={styles.whatsappForm} onSubmit={saveWhatsApp}>
              <div className={styles.phoneRow}>
                <label>
                  Country
                  <select onChange={(event) => setCountry(event.target.value)} value={country}>
                    <option value="IN">India +91</option>
                    <option value="US">United States +1</option>
                    <option value="GB">United Kingdom +44</option>
                    <option value="AE">UAE +971</option>
                    <option value="AU">Australia +61</option>
                    <option value="CA">Canada +1</option>
                  </select>
                </label>
                <label>
                  WhatsApp phone number
                  <input
                    onChange={(event) => setPhone(event.target.value)}
                    placeholder={whatsapp?.masked_number ?? '+91 98765 43210'}
                    required={!whatsapp?.configured || whatsappEnabled}
                    type="tel"
                    value={phone}
                  />
                </label>
              </div>
              <label className={styles.check}>
                <input
                  checked={consent}
                  onChange={(event) => setConsent(event.target.checked)}
                  type="checkbox"
                />
                I confirm this number is mine or I am authorized to receive business notifications.
              </label>
              <label className={styles.toggle}>
                <input
                  checked={whatsappEnabled}
                  onChange={(event) => setWhatsappEnabled(event.target.checked)}
                  type="checkbox"
                />
                <span>Enable WhatsApp lead notifications</span>
              </label>
              <div className={styles.formActions}>
                <button className={styles.primary} disabled={busy === 'whatsapp'} type="submit">
                  Save settings
                </button>
                <button
                  className={styles.secondary}
                  disabled={!whatsapp?.enabled || busy === 'whatsapp-test'}
                  onClick={() => void sendWhatsAppTest()}
                  type="button"
                >
                  Send test notification
                </button>
              </div>
            </form>
          </section>
        </div>
      </div>
    </div>
  );
}
