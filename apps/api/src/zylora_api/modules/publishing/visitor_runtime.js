(() => {
  'use strict';

  const AUTO_DELAY_MS = 10_000;
  const DISMISSED_KEY = 'zylora.lead-form.dismissed';
  const SUBMITTED_KEY = 'zylora.lead-form.submitted';
  const ANALYTICS_SESSION_KEY = 'zylora.analytics.session';

  const readSessionFlag = (key) => {
    try {
      return sessionStorage.getItem(key) === 'true';
    } catch {
      return false;
    }
  };

  const writeSessionFlag = (key) => {
    try {
      sessionStorage.setItem(key, 'true');
    } catch {
      // Session-scoped in-memory state still prevents repeats on this page.
    }
  };

  const uniqueKey = () => {
    const value =
      globalThis.crypto?.randomUUID?.() ??
      `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    return `zylora-form-${value}`;
  };

  const initializeLeadCapture = () => {
    const root = document.querySelector('[data-zylora-lead-controller]');
    if (!(root instanceof HTMLElement)) return;

    const dialog = root.querySelector('[data-zylora-lead-dialog]');
    const form = root.querySelector('[data-zylora-lead-form]');
    const status = root.querySelector('[data-zylora-lead-status]');
    const success = root.querySelector('[data-zylora-lead-success]');
    const submit = form?.querySelector('button[type="submit"]');
    const challenge = form?.querySelector('input[name="turnstile_token"]');
    if (
      !(dialog instanceof HTMLDialogElement) ||
      !(form instanceof HTMLFormElement) ||
      !(status instanceof HTMLElement) ||
      !(success instanceof HTMLElement) ||
      !(submit instanceof HTMLButtonElement) ||
      !(challenge instanceof HTMLInputElement)
    ) {
      return;
    }

    const minimumDelay = Math.max(
      AUTO_DELAY_MS,
      Number.parseInt(root.dataset.autoDelay ?? '', 10) || AUTO_DELAY_MS,
    );
    const challengeRequired = root.dataset.challengeRequired === 'true';
    let analyticsSession = uniqueKey();
    try {
      analyticsSession = sessionStorage.getItem(ANALYTICS_SESSION_KEY) || analyticsSession;
      sessionStorage.setItem(ANALYTICS_SESSION_KEY, analyticsSession);
    } catch {
      // The per-page value remains privacy-safe when storage is unavailable.
    }
    const trackFormOpen = () => {
      void fetch('/api/v1/public/analytics/events', {
        method: 'POST',
        keepalive: true,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_id: uniqueKey(),
          event_type: 'LEAD_FORM_OPENED',
          session_id: analyticsSession,
          page_path: location.pathname || '/',
        }),
      }).catch(() => {});
    };
    let state = readSessionFlag(SUBMITTED_KEY)
      ? 'SUBMITTED'
      : readSessionFlag(DISMISSED_KEY)
        ? 'DISMISSED'
        : 'IDLE';
    let elapsedVisible = 0;
    let visibleSince = document.visibilityState === 'visible' ? Date.now() : null;
    let timer = null;
    let openMode = 'automatic';
    let pendingManual = false;
    let previousFocus = null;

    const setState = (next) => {
      state = next;
      root.dataset.state = next;
    };
    setState(state);

    const clearTimer = () => {
      if (timer !== null) {
        globalThis.clearTimeout(timer);
        timer = null;
      }
    };

    const accumulateVisibleTime = () => {
      if (visibleSince !== null) {
        elapsedVisible += Math.max(0, Date.now() - visibleSince);
        visibleSince = null;
      }
    };

    const anotherModalIsOpen = () =>
      Boolean(
        document.querySelector(
          'dialog[open]:not([data-zylora-lead-dialog]), [aria-modal="true"]:not([data-zylora-lead-dialog])',
        ),
      );

    const chatbotIsActive = () => {
      const panel = document.querySelector('.zylora-chatbot__panel');
      return panel instanceof HTMLElement && !panel.hidden;
    };

    const schedule = (callback, delay) => {
      clearTimer();
      timer = globalThis.setTimeout(callback, delay);
    };

    const show = (mode) => {
      if (dialog.open) return;
      if (mode === 'automatic' && (state === 'DISMISSED' || state === 'SUBMITTED')) return;
      if (anotherModalIsOpen() || (mode === 'automatic' && chatbotIsActive())) {
        pendingManual = mode === 'manual';
        schedule(() => show(mode), 500);
        return;
      }

      pendingManual = false;
      openMode = mode;
      const chatbotPanel = document.querySelector('.zylora-chatbot__panel');
      const chatbotButton = document.querySelector('.zylora-chatbot__open');
      if (chatbotPanel instanceof HTMLElement && chatbotButton instanceof HTMLElement) {
        chatbotPanel.hidden = true;
        chatbotButton.setAttribute('aria-expanded', 'false');
      }
      previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      setState('OPEN');
      dialog.showModal();
      trackFormOpen();
      const focusTarget = form.querySelector('input:not([type="hidden"]), textarea, button');
      if (focusTarget instanceof HTMLElement) focusTarget.focus();
    };

    const tryAutomaticOpen = () => {
      if (state !== 'ELIGIBLE') return;
      if (document.visibilityState !== 'visible') return;
      show('automatic');
    };

    const becomeEligible = () => {
      timer = null;
      accumulateVisibleTime();
      if (elapsedVisible < minimumDelay) {
        visibleSince = document.visibilityState === 'visible' ? Date.now() : null;
        schedule(becomeEligible, minimumDelay - elapsedVisible);
        return;
      }
      setState('ELIGIBLE');
      tryAutomaticOpen();
    };

    const resumeEligibilityTimer = () => {
      if (state !== 'IDLE' && state !== 'ELIGIBLE') return;
      if (document.visibilityState !== 'visible') return;
      visibleSince = Date.now();
      if (state === 'ELIGIBLE') {
        tryAutomaticOpen();
      } else {
        schedule(becomeEligible, Math.max(0, minimumDelay - elapsedVisible));
      }
    };

    const dismiss = () => {
      if (!dialog.open) return;
      if (state !== 'SUBMITTED') {
        writeSessionFlag(DISMISSED_KEY);
        setState('DISMISSED');
      }
      dialog.close();
    };

    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        accumulateVisibleTime();
        clearTimer();
        return;
      }
      resumeEligibilityTimer();
    });

    root.addEventListener('click', (event) => {
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest('[data-zylora-lead-close]')) {
        event.preventDefault();
        dismiss();
      }
    });

    dialog.addEventListener('cancel', (event) => {
      event.preventDefault();
      dismiss();
    });

    dialog.addEventListener('close', () => {
      if (state === 'OPEN') {
        writeSessionFlag(DISMISSED_KEY);
        setState('DISMISSED');
      }
      if (previousFocus?.isConnected) previousFocus.focus();
      previousFocus = null;
    });

    document.addEventListener('click', (event) => {
      const target = event.target instanceof Element ? event.target.closest('a, button') : null;
      if (!(target instanceof HTMLElement)) return;
      const manual =
        target.hasAttribute('data-zylora-lead-open') ||
        (target instanceof HTMLAnchorElement &&
          target.getAttribute('href') === `#${root.dataset.leadTarget ?? ''}`);
      if (!manual) return;
      event.preventDefault();
      show('manual');
    });

    globalThis.zyloraLeadTurnstile = (token) => {
      challenge.value = typeof token === 'string' ? token : '';
      submit.disabled = challengeRequired && !challenge.value;
      status.textContent = '';
    };

    if (challengeRequired) submit.disabled = !challenge.value;

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (challengeRequired && !challenge.value) {
        status.textContent = 'Complete the security check before sending your enquiry.';
        return;
      }
      submit.disabled = true;
      submit.setAttribute('aria-busy', 'true');
      status.textContent = 'Sending your enquiry?';
      const values = new FormData(form);
      try {
        const response = await fetch('/api/v1/public/leads', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Idempotency-Key': uniqueKey(),
          },
          body: JSON.stringify({
            name: String(values.get('name') ?? ''),
            email: String(values.get('email') ?? '') || null,
            phone: String(values.get('phone') ?? '') || null,
            enquiry: String(values.get('enquiry') ?? ''),
            page_path: location.pathname || '/',
            consent: { contact: values.get('contact_consent') === 'on' },
            turnstile_token: challenge.value || null,
          }),
        });
        if (!response.ok) throw new Error('lead_submission_failed');
        const result = await response.json();
        if (result?.source !== 'FORM') throw new Error('lead_source_invalid');
        writeSessionFlag(SUBMITTED_KEY);
        setState('SUBMITTED');
        form.hidden = true;
        success.hidden = false;
        success.focus();
      } catch {
        status.textContent =
          'We could not send your enquiry. Please check your details and try again.';
        submit.disabled = challengeRequired && !challenge.value;
        globalThis.turnstile?.reset?.();
        challenge.value = '';
      } finally {
        submit.removeAttribute('aria-busy');
        if (state !== 'SUBMITTED' && !challengeRequired) submit.disabled = false;
      }
    });

    if (state === 'SUBMITTED') {
      form.hidden = true;
      success.hidden = false;
    } else if (state === 'IDLE') {
      resumeEligibilityTimer();
    }

    root.dataset.ready = 'true';
    root.dataset.openMode = openMode;
    root.dataset.pendingManual = String(pendingManual);
  };

  const initializeChatbot = () => {
    const root = document.querySelector('.zylora-chatbot');
    if (!(root instanceof HTMLElement)) return;
    const open = root.querySelector('.zylora-chatbot__open');
    const panel = root.querySelector('.zylora-chatbot__panel');
    const form = root.querySelector('.zylora-chatbot__form');
    const messages = root.querySelector('.zylora-chatbot__messages');
    const input = form?.querySelector('input[name="message"]');
    if (
      !(open instanceof HTMLButtonElement) ||
      !(panel instanceof HTMLElement) ||
      !(form instanceof HTMLFormElement) ||
      !(messages instanceof HTMLElement) ||
      !(input instanceof HTMLInputElement)
    ) {
      return;
    }

    let conversation;
    const add = (kind, value) => {
      const line = document.createElement('p');
      line.className = `zylora-chatbot__message zylora-chatbot__message--${kind}`;
      line.textContent = value;
      messages.append(line);
      messages.scrollTop = messages.scrollHeight;
    };
    const request = async (url, body) => {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error('chatbot_unavailable');
      return response.json();
    };

    open.addEventListener('click', () => {
      panel.hidden = !panel.hidden;
      open.setAttribute('aria-expanded', String(!panel.hidden));
      if (!panel.hidden) input.focus();
    });

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const message = input.value.trim();
      if (!message) return;
      input.value = '';
      add('visitor', message);
      try {
        if (!conversation) {
          conversation = await request('/api/v1/public/chatbot/conversations', {});
        }
        const reply = await request(
          `/api/v1/public/chatbot/conversations/${conversation.id}/messages`,
          { access_token: conversation.access_token, message },
        );
        add('assistant', reply.answer);
      } catch {
        add('system', 'The assistant is unavailable right now. You can use the enquiry form.');
      }
    });
  };

  const initialize = () => {
    initializeLeadCapture();
    initializeChatbot();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
})();
