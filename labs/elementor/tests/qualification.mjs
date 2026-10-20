import { test } from '@playwright/test';

// Explicit boundary: ONLY qualifying product assertions belong in this callback.
// Navigation, setup, fixture creation, and probe I/O stay outside.
export async function productAssertion(identity, assertProduct) {
  if (!/^[A-O]:[a-z0-9-]+$/.test(identity)) {
    throw new Error('Invalid qualified product assertion identity');
  }
  return test.step('EV4_PRODUCT_ASSERTION:' + identity, assertProduct);
}
