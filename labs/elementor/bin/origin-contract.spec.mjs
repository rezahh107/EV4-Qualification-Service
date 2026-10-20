import fs from 'node:fs';
import assert from 'node:assert/strict';
import { test, expect } from '@playwright/test';
import { observe, receiptPath } from '../tests/observation.mjs';
import { productAssertion } from '../tests/qualification.mjs';

const identity='C:measured-geometry';
function status(kind) {
  return JSON.parse(fs.readFileSync(receiptPath(identity,kind),'utf8')).state;
}

test('complete negative product snapshot is a recognized matcher failure', async () => {
  test.fail();
  const data=await observe(identity,async()=>({width:4,height:26}));
  await productAssertion(identity,data,snapshot=>{
    expect(snapshot.width).toBeGreaterThan(5);
    expect(snapshot.height).toBeGreaterThan(5);
  });
});
test('complete negative receipt survives the expected failing assertion', async () => {
  assert.equal(status('observation'),'COMPLETE');
  assert.equal(status('assertion'),'PRODUCT_FAIL');
});

test('unavailable acquisition has no product assertion', async () => {
  test.fail();
  await observe(identity,async()=>{throw new Error('Simulated browser transport interruption');});
});
test('acquisition failure remains unqualified', async () => {
  assert.equal(status('observation'),'UNAVAILABLE');
  assert.equal(status('assertion'),'NOT_EXECUTED');
});

test('unexpected exception in product callback cannot impersonate matcher failure', async () => {
  test.fail();
  const data=await observe(identity,async()=>({width:20,height:26}));
  await productAssertion(identity,data,_snapshot=>{
    throw new TypeError('Unexpected callback execution error');
  });
});
test('generic callback error recorded as unproven', async () => {
  assert.equal(status('observation'),'COMPLETE');
  assert.equal(status('assertion'),'UNPROVEN');
});

test('negated Playwright matcher failure is still a genuine matcher failure', async () => {
  test.fail();
  const data=await observe(identity,async()=>null);
  await productAssertion(identity,data,snapshot=>{
    expect(snapshot).not.toBeNull();
  });
});
test('negated mismatch does not become infrastructure unavailability', async () => {
  assert.equal(status('assertion'),'PRODUCT_FAIL');
});

test('complete valid data produces a genuine product PASS', async () => {
  const data=await observe(identity,async()=>({width:25,height:26}));
  await productAssertion(identity,data,snapshot=>{
    expect(snapshot.width).toBeGreaterThan(5);
    expect(snapshot.height).toBeGreaterThan(5);
  });
  assert.equal(status('observation'),'COMPLETE');
  assert.equal(status('assertion'),'PRODUCT_PASS');
});
