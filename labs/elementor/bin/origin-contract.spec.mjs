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
      width,pageWidth:width,left:0,right:width-1,height:[128,96,64,32][index],
      accent:{text:accent,color,visible:true,width:90,height:22}
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
  for(const [name,mutate] of Object.entries({
    'mobile missing accent': r=>{r.accent={text:null,color:null,visible:false,width:null,height:null};},
    'mobile wrong color': r=>{r.accent.color='rgb(0, 0, 0)';},
    'mobile wrong substring': r=>{r.accent.text='Intelligence';},
    'mobile invisible with nonzero geometry': r=>{r.accent.visible=false;},
    'mobile zero-width': r=>{r.accent.width=0;},
  })){
    const candidate=structuredClone(snapshot);
    mutate(candidate.responsive[0]);
    assert.throws(()=>predicate(candidate),error=>error?.matcherResult?.pass===false,
      'repaired D predicate rejects '+name);
  }
});


test('real CSS mobile-only hidden accent cannot qualify through the actual D predicate', async ({page}) => {
  // Browser DOM CSS evidence from a controlled fixture, not native Elementor.
  // Extract the *actual* D per-viewport evaluate callback from reviewed source.
  const source=fs.readFileSync(new URL('../tests/native.spec.mjs', import.meta.url),'utf8');
  const syntax=parse(source,{ecmaVersion:2025,sourceType:'module'});
  const d=syntax.body.find(node=>node.type==='ExpressionStatement' &&
    node.expression?.callee?.name==='test' &&
    node.expression.arguments[0]?.value?.startsWith('[D:native-partial-text-colors]'));
  assert.ok(d);
  const evaluations=[],assertions=[];
  function walk(node) {
    if(!node||typeof node!=='object')return;
    if(node.type==='CallExpression'&&node.callee?.type==='MemberExpression'&&
       node.callee.property?.name==='evaluate'&&node.arguments[0]?.type==='ArrowFunctionExpression'){
      evaluations.push(node.arguments[0]);
    }
    if(node.type==='CallExpression'&&node.callee?.name==='productAssertion'&&
       node.arguments[0]?.value===partialIdentity)assertions.push(node.arguments[2]);
    for(const [key,value] of Object.entries(node)){
      if(['start','end','raw','loc','range'].includes(key))continue;
      if(Array.isArray(value))value.forEach(walk);
      else if(value&&typeof value==='object')walk(value);
    }
  }
  walk(d.expression.arguments[1].body);
  const realAccentCallbacks=evaluations.filter(n=>
    source.slice(n.start,n.end).includes('checkVisibility('));
  assert.equal(realAccentCallbacks.length,1);
  assert.equal(assertions.length,1);
  const collect=runInNewContext('('+source.slice(realAccentCallbacks[0].start,
    realAccentCallbacks[0].end)+')');
  const predicate=runInNewContext('('+source.slice(assertions[0].start,
    assertions[0].end)+')',{expect});
  const ordinary='Smart Homes Are Connected. Now They Need ';
  const accent='Intelligence.';
  const accentColor='rgb(180, 35, 78)';
  const markup=ordinary+'<span style="color: #b4234e;">'+accent+'</span>';
  const base={
    atomic:{widgetType:'e-heading',selection:accent,qualification:'NOT_PROVEN'},
    legacy:{widgetType:'heading',authoredVia:'native-title-control',
      editorReopened:1,editorTitle:markup},
    semanticHeadings:1,accessibleHeadings:1,
    published:{tag:'H2',text:ordinary+accent,ordinaryText:ordinary,
      accentText:accent,spanCount:1,directChildCount:2,childElements:1,
      accentColor,ordinaryColor:'rgb(110, 193, 228)'},
    expected:{fullText:ordinary+accent,ordinary,accented:accent,
      accentColor,authoredMarkup:markup}
  };
  await page.setContent('<style>body{margin:0}h2{box-sizing:border-box;width:calc(100% - 20px);max-width:1140px;margin:0 auto;font:32px/1.3 Arial;color:rgb(110,193,228)}</style>'+
    '<h2>'+markup+'</h2>');
  async function record() {
    const responsive=[];
    for(const width of [320,390,768,1440]){
      await page.setViewportSize({width,height:900});
      const heading=page.locator('h2');
      const box=await heading.boundingBox();
      responsive.push({width,pageWidth:await page.evaluate(()=>document.documentElement.scrollWidth),
        left:box.x,right:box.x+box.width,height:box.height,
        accent:await heading.evaluate(collect)});
    }
    return {...base,responsive};
  }
  const clean=await record();
  assert.doesNotThrow(()=>predicate(clean),'true browser-observed visible accent');
  const style=await page.addStyleTag({content:'@media(max-width:400px){h2 span{display:none}}'});
  const hidden=await record();
  assert.equal(hidden.responsive[0].accent.visible,false);
  assert.equal(hidden.responsive[1].accent.visible,false);
  assert.equal(hidden.responsive[2].accent.visible,true);
  assert.equal(hidden.responsive[3].accent.visible,true);
  for(const item of hidden.responsive){
    assert.ok(item.left>=-1&&item.right<=item.width+1);
    assert.ok(item.pageWidth<=item.width+1);
    assert.ok(item.height>0);
  }
  assert.ok(hidden.responsive[0].height>hidden.responsive[3].height);
  assert.throws(()=>predicate(hidden),e=>e?.matcherResult?.pass===false,
    'display:none only on mobile cannot qualify');
  await style.evaluate(node=>node.textContent='@media(max-width:400px){h2 span{visibility:hidden}}');
  const hiddenVisibility=await record();
  assert.equal(hiddenVisibility.responsive[0].accent.visible,false);
  assert.ok(hiddenVisibility.responsive[0].accent.width>0);
  assert.equal(hiddenVisibility.responsive[0].accent.color,accentColor);
  assert.throws(()=>predicate(hiddenVisibility),e=>e?.matcherResult?.pass===false,
    'visibility:hidden with correct color and nonzero geometry cannot qualify');
  await style.evaluate(node=>node.textContent='@media(max-width:400px){h2 span{opacity:0}}');
  const hiddenOpacity=await record();
  assert.equal(hiddenOpacity.responsive[0].accent.visible,false);
  assert.throws(()=>predicate(hiddenOpacity),e=>e?.matcherResult?.pass===false,
    'opacity:0 with correct color and geometry cannot qualify');
});

test('visible-but-stale Title races through visibility-only acquisition',async({page})=>{
  // Controlled mock: never infer a defect in real native Elementor from this.
  await page.setContent('<div class="elementor-control-title"><input value="Previous widget value"></div>');
  const title=page.locator(partialSelector).first();
  await page.evaluate(()=>{
    setTimeout(()=>{
      document.querySelector('.elementor-control-title input').value='New selected widget value';
    },350);
  });
  await expect(title).toBeVisible({timeout:1500});
  const premature=await title.inputValue();
  assert.equal(premature,'Previous widget value',
    'visibility-only readiness samples old value despite visible control');
  await expect(title).toHaveValue('New selected widget value',{timeout:2500});
  assert.equal(await title.inputValue(),'New selected widget value');
  // Waiting for the desired text is only a controlled-test discriminator;
  // it is NOT an admissible production readiness signal.
});


test('selection and panel identity alone do not make a visible stale Title ready',async({page})=>{
  // Controlled panel stand-in only; not proof about native Elementor timing.
  await page.setContent('<div class="elementor-control-title"><input value="Previous widget"></div>');
  await page.evaluate(()=>{
    const old={id:'old',settings:{get:()=> 'Previous widget'}};
    window._testState={selected:old,panel:old,page:'editor'};
    window.elementor={
      selection:{getElements:()=>[window._testState.selected]},
      getPanelView:()=>({
        getCurrentPageName:()=>window._testState.page,
        getCurrentPageView:()=>({
          getOption:()=>({getContainer:()=>window._testState.panel})
        })
      })
    };
  });
  const readiness=async()=>page.evaluate(target=>{
    const panel=window.elementor.getPanelView();
    const selected=window.elementor.selection.getElements();
    const edited=panel.getCurrentPageView().getOption('editedElementView').getContainer();
    const input=document.querySelector('.elementor-control-title input');
    return selected.length===1&&selected[0].id===target&&
      panel.getCurrentPageName()==='editor'&&edited.id===target&&
      input?.getClientRects().length>0&&input.value===edited.settings.get('title');
  },'target');
  await page.evaluate(()=>{
    const updated={id:'target',settings:{get:()=> 'New widget'}};
    window._testState.selected=updated;
    window._testState.panel=updated;
  });
  const input=page.locator(partialSelector).first();
  await expect(input).toBeVisible();
  assert.equal(await input.inputValue(),'Previous widget');
  assert.equal(await readiness(),false,'identity-only would read stale control');
  await page.evaluate(()=>{setTimeout(()=>{
    document.querySelector('.elementor-control-title input').value='New widget';
  },180)});
  await expect.poll(readiness,{timeout:2000}).toBe(true);
  assert.equal(await input.inputValue(),'New widget');
  // When native model and control agree on a genuinely incorrect value, the
  // acquisition must complete; the product assertion still owns the failure.
  await page.evaluate(()=>{
    const wrong={id:'target',settings:{get:()=> 'Wrong saved widget title'}};
    window._testState.selected=wrong;window._testState.panel=wrong;
    document.querySelector('.elementor-control-title input').value='Wrong saved widget title';
  });
  assert.equal(await readiness(),true);
  const wrong=await input.inputValue();
  assert.notEqual(wrong,'Expected title');
  assert.throws(()=>expect(wrong).toBe('Expected title'),
    e=>e?.matcherResult?.pass===false);
});
