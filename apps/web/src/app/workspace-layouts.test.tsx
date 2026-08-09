import { describe, expect, it } from 'vitest';

import { metadata as userMetadata } from './app/layout';
import { metadata as adminMetadata } from './admin/(portal)/layout';

describe('private workspace metadata', () => {
  it('keeps both authenticated applications out of search indexes', () => {
    expect(userMetadata.robots).toMatchObject({ index: false, follow: false });
    expect(adminMetadata.robots).toMatchObject({ index: false, follow: false });
  });
});
