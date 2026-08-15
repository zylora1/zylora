import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AI_PROMPT_STORAGE_KEY } from '@/lib/ai-builder';
import { AiBuilderProject } from './ai-builder-project';

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  csrfToken: vi.fn(),
}));

vi.mock('@/lib/api', () => ({ apiRequest: mocks.apiRequest, csrfToken: mocks.csrfToken }));

function project(overrides: Record<string, unknown> = {}) {
  return {
    id: '019ff9d0-1578-7dc7-8c1f-fff23b2f4904',
    status: 'QUEUED',
    generation_id: 'dd86f0e6-e1c2-4629-8ae9-6817234eaba6',
    generation_version: 1,
    attempt: 0,
    max_attempts: 4,
    retryable: false,
    can_cancel: true,
    can_retry: false,
    preview_ready: false,
    artifact_digest: null,
    safe_error_code: null,
    safe_error_message: null,
    queued_at: '2026-08-13T06:00:00Z',
    started_at: null,
    completed_at: null,
    failed_at: null,
    cancelled_at: null,
    created_at: '2026-08-13T06:00:00Z',
    updated_at: '2026-08-13T06:00:00Z',
    ...overrides,
  };
}

describe('AiBuilderProject durable states', () => {
  beforeEach(() => {
    mocks.apiRequest.mockReset();
    mocks.csrfToken.mockReset();
    window.sessionStorage.clear();
  });

  afterEach(() => vi.useRealTimers());

  it('restores the authenticated server state and preserved prompt after a fresh mount', async () => {
    window.sessionStorage.setItem(
      AI_PROMPT_STORAGE_KEY,
      'A durable clinic website with appointments.',
    );
    mocks.apiRequest.mockResolvedValue({ items: [project()] });

    render(<AiBuilderProject />);

    expect(
      await screen.findByDisplayValue('A durable clinic website with appointments.'),
    ).toBeVisible();
    expect(await screen.findByText('Queued')).toBeVisible();
    expect(screen.getByText(/attempt 0 of 4/)).toBeVisible();
    expect(mocks.apiRequest).toHaveBeenCalledWith('/api/v1/ai-site-projects');
  });

  it('uses persisted polling results instead of a client completion timer', async () => {
    vi.useFakeTimers();
    const completed = project({
      status: 'COMPLETED',
      attempt: 1,
      can_cancel: false,
      preview_ready: true,
      artifact_digest: 'a'.repeat(64),
      completed_at: '2026-08-13T06:01:00Z',
    });
    mocks.apiRequest
      .mockResolvedValueOnce({ items: [project({ status: 'GENERATING', attempt: 1 })] })
      .mockResolvedValueOnce(completed);

    render(<AiBuilderProject />);
    await act(async () => Promise.resolve());
    expect(screen.getByText('Generating')).toBeVisible();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(screen.getByText('Preview ready')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Open artifact' })).toBeVisible();
    expect(mocks.apiRequest).toHaveBeenLastCalledWith(
      '/api/v1/ai-site-projects/019ff9d0-1578-7dc7-8c1f-fff23b2f4904',
    );
  });

  it('keeps the last persisted state when a poll is temporarily unavailable', async () => {
    vi.useFakeTimers();
    mocks.apiRequest
      .mockResolvedValueOnce({ items: [project({ status: 'BUILDING' })] })
      .mockRejectedValueOnce(new Error('temporary'));

    render(<AiBuilderProject />);
    await act(async () => Promise.resolve());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(screen.getByText('Building')).toBeVisible();
  });

  it('submits a trimmed prompt with CSRF and clears only after durable acceptance', async () => {
    const prompt = '  A production website for a family dental practice.  ';
    window.sessionStorage.setItem(AI_PROMPT_STORAGE_KEY, prompt);
    mocks.csrfToken.mockReturnValue('csrf-token');
    mocks.apiRequest.mockResolvedValueOnce({ items: [] }).mockResolvedValueOnce(project());

    render(<AiBuilderProject />);
    const input = await screen.findByLabelText('What should this website accomplish?');
    await waitFor(() => expect(input).toHaveValue(prompt.trim()));
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => expect(mocks.apiRequest).toHaveBeenCalledTimes(2));
    const [url, options] = mocks.apiRequest.mock.calls[1]!;
    expect(url).toBe('/api/v1/ai-site-projects');
    expect(options).toMatchObject({
      method: 'POST',
      headers: { 'X-CSRF-Token': 'csrf-token' },
      body: JSON.stringify({ prompt: prompt.trim() }),
    });
    expect(options.headers['Idempotency-Key']).toMatch(/^ai-site-/);
    expect(await screen.findByRole('status')).toHaveTextContent('durable generation is queued');
    expect(input).toHaveValue('');
    expect(window.sessionStorage.getItem(AI_PROMPT_STORAGE_KEY)).toBeNull();
  });

  it('shows safe submission failures and retains the prompt for retry', async () => {
    mocks.apiRequest.mockResolvedValueOnce({ items: [] }).mockRejectedValueOnce('failed');
    render(<AiBuilderProject />);
    const input = await screen.findByLabelText('What should this website accomplish?');
    fireEvent.change(input, { target: { value: 'A valid website prompt that should remain.' } });
    fireEvent.submit(input.closest('form')!);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The AI website project could not be queued.',
    );
    expect(input).toHaveValue('A valid website prompt that should remain.');
  });

  it('sends owner cancellation with CSRF and displays the authoritative result', async () => {
    mocks.csrfToken.mockReturnValue('csrf-token');
    mocks.apiRequest
      .mockResolvedValueOnce({ items: [project()] })
      .mockResolvedValueOnce(project({ status: 'CANCELLED', can_cancel: false }));

    render(<AiBuilderProject />);
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }));

    await waitFor(() =>
      expect(mocks.apiRequest).toHaveBeenLastCalledWith(
        '/api/v1/ai-site-projects/019ff9d0-1578-7dc7-8c1f-fff23b2f4904/cancel',
        { method: 'POST', headers: { 'X-CSRF-Token': 'csrf-token' } },
      ),
    );
    expect(await screen.findByText('Cancelled')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument();
  });

  it('retries an eligible failed version with a new idempotency key', async () => {
    mocks.apiRequest
      .mockResolvedValueOnce({
        items: [
          project({
            status: 'FAILED',
            retryable: true,
            can_cancel: false,
            can_retry: true,
            safe_error_message: 'The generation provider is temporarily unavailable.',
          }),
        ],
      })
      .mockResolvedValueOnce(project({ generation_version: 2 }));

    render(<AiBuilderProject />);
    expect(
      await screen.findByText('The generation provider is temporarily unavailable.'),
    ).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    await waitFor(() => expect(mocks.apiRequest).toHaveBeenCalledTimes(2));
    const [, options] = mocks.apiRequest.mock.calls[1]!;
    expect(options.method).toBe('POST');
    expect(options.headers['Idempotency-Key']).toMatch(/^ai-retry-/);
    expect(await screen.findByText('Queued')).toBeVisible();
  });

  it('opens only the server-authorized artifact URL and surfaces access failures', async () => {
    const ready = project({ status: 'COMPLETED', can_cancel: false, preview_ready: true });
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);
    mocks.apiRequest
      .mockResolvedValueOnce({ items: [ready] })
      .mockResolvedValueOnce({ download_url: 'https://objects.example/signed-artifact' })
      .mockRejectedValueOnce(new Error('Preview is temporarily unavailable.'));

    render(<AiBuilderProject />);
    const button = await screen.findByRole('button', { name: 'Open artifact' });
    fireEvent.click(button);
    await waitFor(() =>
      expect(open).toHaveBeenCalledWith(
        'https://objects.example/signed-artifact',
        '_blank',
        'noopener,noreferrer',
      ),
    );
    fireEvent.click(button);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Preview is temporarily unavailable.',
    );
    open.mockRestore();
  });

  it('fails closed to an empty queue when the initial status read is unavailable', async () => {
    mocks.apiRequest.mockRejectedValue(new Error('offline'));
    render(<AiBuilderProject />);
    expect(await screen.findByText(/No AI website projects yet/)).toBeVisible();
  });
});
