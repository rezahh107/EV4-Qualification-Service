import fs from 'node:fs';
import assert from 'node:assert/strict';
import { runInNewContext } from 'node:vm';
import { parse } from 'acorn';
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

test('actual D predicate rejects left-clipped geometry despite passing right and document widths', () => {
  // Isolated predicate mutation, NOT a browser observation or Elementor claim.
  // Execute the exact reviewed callback from native.spec.mjs, not a copied
  // approximation that could diverge from the real admission predicate.
  const source=fs.readFileSync(new URL('../tests/native.spec.mjs', import.meta.url),'utf8');
  const syntax=parse(source,{ecmaVersion:2025,sourceType:'module'});
  const declarations=syntax.body.filter(node=>
    node.type==='ExpressionStatement' &&
    node.expression?.callee?.name==='test' &&
    node.expression.arguments[0]?.value?.startsWith('[D:native-partial-text-colors]'));
  assert.equal(declarations.length,1);
  const callbacks=[];
  function walk(node) {
    if(!node || typeof node!=='object')return;
    if(node.type==='CallExpression' && node.callee?.name==='productAssertion' &&
       node.arguments[0]?.value===partialIdentity)callbacks.push(node.arguments[2]);
    for(const [key,value] of Object.entries(node)) {
      if(['start','end','raw','loc','range'].includes(key))continue;
      if(Array.isArray(value))value.forEach(walk);
      else if(value && typeof value==='object')walk(value);
    }
  }
  walk(declarations[0].expression.arguments[1].body);
  assert.equal(callbacks.length,1);
  const callback=callbacks[0];
  const predicate=runInNewContext('('+source.slice(callback.start,callback.end)+')',{expect});
  const ordinary='Smart Homes Are Connected. Now They Need ';
  const accent='Intelligence.';
  const color='rgb(180, 35, 78)';
  const title=ordinary+'<span style="color: #b4234e;">'+accent+'</span>';
  const snapshot={
    atomic:{widgetType:'e-heading',selection:accent,qualification:'NOT_PROVEN'},
    legacy:{widgetType:'heading',authoredVia:'native-title-control',
      editorReopened:1,editorTitle:title},
    semanticHeadings:1,accessibleHeadings:1,
    published:{tag:'H2',text:ordinary+accent,ordinaryText:ordinary,
      accentText:accent,spanCount:1,directChildCount:2,childElements:1,
      accentColor:color,ordinaryColor:'rgb(110, 193, 228)'},
    responsive:[320,390,768,1440].map((width,index)=>({
      width,pageWidth:width,left:0,right:width-1,height:[128,96,64,32][index]
    })),
    expected:{fullText:ordinary+accent,ordinary,accented:accent,
      accentColor:color,authoredMarkup:title}
  };
  assert.doesNotThrow(()=>predicate(snapshot),'all four positive viewports');
  const atTolerance=structuredClone(snapshot);
  atTolerance.responsive[0].left=-1;
  assert.doesNotThrow(()=>predicate(atTolerance),'K-equivalent -1px tolerance');
  const clipped=structuredClone(snapshot);
  clipped.responsive[0].left=-12;
  // Every other geometry condition is deliberately still satisfied.
  assert.equal(clipped.responsive[0].right,319);
  assert.equal(clipped.responsive[0].pageWidth,320);
  assert.ok(clipped.responsive[0].height>0);
  assert.throws(()=>predicate(clipped),error=>error?.matcherResult?.pass===false,
    'the *actual* product predicate must reject left clipping');
});
