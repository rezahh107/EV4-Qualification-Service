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


const partialIdentity = 'D:native-partial-text-colors';
const partialSelector = '.elementor-control-title input, .elementor-control-title textarea';

test('delayed native-title-shaped control is sampled only after web-first readiness', async ({page}) => {
  // Controlled DOM timing only: NOT evidence of actual Elementor support.
  await page.setContent('<div id="editor-panel"></div>');
  await page.evaluate(() => {
    setTimeout(() => {
      const control = document.createElement('div');
      control.className = 'elementor-control-title';
      const title = document.createElement('input');
      title.value = 'Smart Homes Are Connected. Now They Need Intelligence.';
      control.append(title);
      document.querySelector('#editor-panel').append(control);
    }, 250);
  });
  const reopenedInput = page.locator(partialSelector).first();
  const snapshot = await observe(partialIdentity, async () => {
    await expect(reopenedInput).toBeVisible({timeout:2000});
    return {editorTitle:await reopenedInput.inputValue()};
  });
  await productAssertion(partialIdentity, snapshot, value => {
    expect(value.editorTitle).toBe('Smart Homes Are Connected. Now They Need Intelligence.');
  });
  assert.notEqual(snapshot.editorTitle, null);
  assert.equal(statusFor(partialIdentity, 'observation'), 'COMPLETE');
  assert.equal(statusFor(partialIdentity, 'assertion'), 'PRODUCT_PASS');
});

test('unavailable native-title-shaped control remains unproven, never a product failure', async ({page}) => {
  // This probes acquisition semantics, not a native product assertion.
  await page.setContent('<div id="editor-panel"></div>');
  const reopenedInput = page.locator(partialSelector).first();
  await assert.rejects(observe(partialIdentity, async () => {
    await expect(reopenedInput).toBeVisible({timeout:300});
    return {editorTitle:await reopenedInput.inputValue()};
  }), /toBeVisible/);
  assert.equal(statusFor(partialIdentity, 'observation'), 'UNAVAILABLE');
  assert.equal(statusFor(partialIdentity, 'assertion'), 'NOT_EXECUTED');
});

function statusFor(identity, kind) {
  return JSON.parse(fs.readFileSync(receiptPath(identity, kind),'utf8')).state;
}
