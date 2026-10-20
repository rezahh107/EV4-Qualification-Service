import { expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const directory = path.resolve('artifacts/observation-provenance');
export const identityPattern = /^[A-O]:[a-z0-9-]+$/;
export function receiptPath(identity, kind) {
  if (!identityPattern.test(identity) || !['observation', 'assertion'].includes(kind))
    throw new Error('Invalid evidence receipt identity');
  return path.join(directory, identity.replace(':', '__') + '.' + kind + '.json');
}
export function fingerprint(value) {
  return crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');
}
export function plainData(value, depth = 0) {
  if (depth > 30) throw new Error('Observation nesting unsupported');
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (Array.isArray(value)) return value.map(item => plainData(item, depth + 1));
  if (value && Object.getPrototypeOf(value) === Object.prototype) {
    const result = {};
    for (const [key, item] of Object.entries(value)) {
      if (['__proto__', 'constructor', 'prototype'].includes(key)) throw new Error('Unsafe observation key');
      result[key] = plainData(item, depth + 1);
    }
    return result;
  }
  throw new Error('Observation is not completed plain JSON data');
}
export function writeReceipt(identity, kind, contents) {
  fs.mkdirSync(directory, {recursive:true});
  fs.writeFileSync(receiptPath(identity, kind), JSON.stringify(contents, null, 2) + '\n');
}
export async function observe(identity, collect) {
  if (!identityPattern.test(identity)) throw new Error('Invalid observation identity');
  // Avoid stale evidence when an individual test fails before qualification.
  writeReceipt(identity, 'observation', {state:'ACQUIRING', identity});
  writeReceipt(identity, 'assertion', {state:'NOT_EXECUTED', identity});
  try {
    const value = plainData(await collect());
    const sha256 = fingerprint(value);
    writeReceipt(identity, 'observation', {state:'COMPLETE', identity, sha256, value});
    return value;
  } catch (error) {
    writeReceipt(identity, 'observation', {state:'UNAVAILABLE', identity,
      error_name:String(error?.name || 'Error').slice(0,120)});
    throw error;
  }
}

// Preserve Playwright's useful retry behavior without making its matcher
// exception a product-failure signal. A successful subsequent count() is a
// completed negative or positive observation; a transport error still throws.
export async function settledCount(locator, expected, timeout = 12000) {
  try {
    await expect(locator).toHaveCount(expected, {timeout});
  } catch (_error) {
    // Re-acquire below; never infer product failure from a timeout alone.
  }
  return locator.count();
}
