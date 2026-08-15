import assert from 'node:assert/strict';
import test from 'node:test';

import { bearerAuthorized } from '../src/security/service-auth.mjs';

const token = 'builder-service-token-000000000001';

test('internal Builder endpoints require an exact bearer service token', () => {
  assert.equal(bearerAuthorized(undefined, token), false);
  assert.equal(bearerAuthorized('Bearer wrong-token', token), false);
  assert.equal(bearerAuthorized(`Bearer ${token}`, token), true);
});
