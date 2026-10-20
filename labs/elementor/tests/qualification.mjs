import fs from 'node:fs';
import { test } from '@playwright/test';
import { fingerprint, receiptPath, writeReceipt, identityPattern } from './observation.mjs';

// Product qualification consumes only completed, JSON-safe observation data.
// The source AST contract enforces pure synchronous Playwright value predicates.
export async function productAssertion(identity, observation, assertProduct) {
  if (!identityPattern.test(identity)) throw new Error('Invalid qualification identity');
  let receipt;
  try {
    receipt = JSON.parse(fs.readFileSync(receiptPath(identity, 'observation'), 'utf8'));
  } catch {
    throw new Error('Missing complete observation evidence');
  }
  if (receipt.state !== 'COMPLETE' || receipt.identity !== identity ||
      receipt.sha256 !== fingerprint(observation))
    throw new Error('Unproven observation provenance');
  return test.step('EV4_PRODUCT_ASSERTION:' + identity, async () => {
    try {
      // The validator forbids async callbacks, browser APIs and helper calls here.
      const returned = assertProduct(observation);
      if (returned !== undefined) throw new Error('Product predicates must be synchronous');
      writeReceipt(identity, 'assertion', {state:'PRODUCT_PASS', identity,
        observation_sha256:receipt.sha256});
    } catch (error) {
      // matcherResult is a structured Playwright Expect failure discriminator.
      // A generic TypeError, transport error or harness crash is not product failure.
      const isMatcherFailure = error?.matcherResult?.pass === false;
      writeReceipt(identity, 'assertion', {
        state:isMatcherFailure ? 'PRODUCT_FAIL' : 'UNPROVEN',
        identity, observation_sha256:receipt.sha256,
      });
      throw error;
    }
  });
}
