import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import { createAtomicFixture } from './helpers.mjs';
import { productAssertion } from './qualification.mjs';
import { observe, settledCount } from './observation.mjs';

const postId = process.env.LAB_PAGE_ID;
const title = 'EV4 Atomic Heading';
const frontend = '/?page_id=' + postId;

test('[O:installed-runtime-browser] real WordPress HTTP form responds',async({page,browser})=>{
 fs.mkdirSync('./artifacts',{recursive:true});
 fs.writeFileSync('./artifacts/browser.json',JSON.stringify({engine:'chromium',version:browser.version()},null,2));
 const observation=await observe('O:installed-runtime-browser',async()=>{
  const response=await page.goto('/wp-login.php');
  return {httpStatus:response?.status()??null,
   loginVisible:await page.locator('#user_login').isVisible(),
   passwordVisible:await page.locator('#user_pass').isVisible()};
 });
 await productAssertion('O:installed-runtime-browser',observation,snapshot=>{
  expect(snapshot.httpStatus).toBe(200);
  expect(snapshot.loginVisible).toBe(true);
  expect(snapshot.passwordVisible).toBe(true);
 });
});

test('[M:native-editor-create-reopen] actual Elementor editor authoring and persistence',async({page})=>{
 expect(postId).toMatch(/^\d+$/);
 const {root,ids}=await createAtomicFixture(page,postId);
 const frame=page.frameLocator('#elementor-preview-iframe');
 const heading=frame.locator('[data-id="'+ids.atomic+'"]');
 await expect(heading).toBeVisible();
 await heading.locator('h2').dblclick();
 const editor=frame.locator('.ProseMirror[contenteditable="true"]');
 await expect(editor).toBeVisible();
 await editor.fill(title);
 await page.keyboard.press('Escape');
 await expect(heading).toContainText(title);
 const publish=root.getByRole('button',{name:/^Publish$/i}).first();
 await expect(publish).toBeEnabled();
 await publish.click();
 await expect(publish).toBeDisabled({timeout:30000});
 await page.reload();
 await expect(frame.locator('[data-id="'+ids.atomic+'"] h2')).toContainText(title,{timeout:60000});
 const observation=await observe('M:native-editor-create-reopen',async()=>{
  await page.goto(frontend);
  const headings=page.locator('h2.e-heading-base');
  await settledCount(headings,1);
  return {count:await headings.count(), text:await headings.first().textContent(), expected:title};
 });
 await productAssertion('M:native-editor-create-reopen',observation,snapshot=>{
  expect(snapshot.count).toBe(1);
  expect(snapshot.text).toBe(snapshot.expected);
 });
 fs.mkdirSync('./artifacts',{recursive:true});
 fs.writeFileSync('./artifacts/element-ids.json',JSON.stringify(ids,null,2));
});

test('[A:native-parent-child] actual published V4 element retains parent',async({page})=>{
 const observation=await observe('A:native-parent-child',async()=>{
  await page.goto(frontend);
  const heading=page.locator('h2.e-heading-base').first();
  await heading.waitFor({state:'attached',timeout:15000});
  const ids=JSON.parse(fs.readFileSync('./artifacts/element-ids.json','utf8'));
  const data=await heading.evaluate(node=>{
    const parent=node.closest('[data-element_type="container"]');
    return {atomicId:node.getAttribute('data-interaction-id'),
      parentId:parent?.getAttribute('data-id'),text:node.textContent};
  });
  return {...data,expectedAtomic:ids.atomic,expectedParent:ids.container,expectedText:title};
 });
 await productAssertion('A:native-parent-child',observation,snapshot=>{
  expect(snapshot.atomicId).toBe(snapshot.expectedAtomic);
  expect(snapshot.parentId).toBe(snapshot.expectedParent);
  expect(snapshot.text).toBe(snapshot.expectedText);
 });
});

test('[B:native-flex-container] native published flex layout is computed',async({page})=>{
 const observation=await observe('B:native-flex-container',async()=>{
  await page.goto(frontend);
  return {display:await page.locator('.e-heading-base').first().evaluate(node=>{
    const container=node.closest('.e-con');
    return container ? getComputedStyle(container).display : null;
   })};
 });
 await productAssertion('B:native-flex-container',observation,snapshot=>{
  expect(snapshot.display).toBe('flex');
 });
});

test('[C:measured-geometry] published heading occupies nonzero bounds',async({page})=>{
 const observation=await observe('C:measured-geometry',async()=>{
  await page.goto(frontend);
  return await page.locator('h2.e-heading-base').first().boundingBox();
 });
 await productAssertion('C:measured-geometry',observation,snapshot=>{
  expect(snapshot).not.toBeNull();
  expect(snapshot?.width).toBeGreaterThan(5);
  expect(snapshot?.height).toBeGreaterThan(5);
 });
});

test('[D:atomic-semantic-heading] atomic widget uses semantic H2',async({page})=>{
 const observation=await observe('D:atomic-semantic-heading',async()=>{
  await page.goto(frontend);
  const heading=page.locator('h2.e-heading-base').first();
  await settledCount(page.locator('h2.e-heading-base'),1);
  const actual=await heading.count();
  return {count:actual,tag:actual?await heading.evaluate(node=>node.tagName):null,
   text:actual?await heading.textContent():null,
   roleCount:await page.getByRole('heading',{name:title,level:2}).count()};
 });
 await productAssertion('D:atomic-semantic-heading',observation,snapshot=>{
  expect(snapshot.count).toBe(1);
  expect(snapshot.tag).toBe('H2');
  expect(snapshot.text).toBe('EV4 Atomic Heading');
  expect(snapshot.roleCount).toBe(1);
 });
});

test('[I:native-link-activation] native Elementor link activates anchor',async({page})=>{
 const observation=await observe('I:native-link-activation',async()=>{
  await page.goto(frontend);
  const link=page.locator('.elementor-button-link[href="#ev4-anchor"]').first();
  const count=await link.count();
  if(count) await link.click();
  return {count,url:page.url()};
 });
 await productAssertion('I:native-link-activation',observation,snapshot=>{
  expect(snapshot.count).toBe(1);
  expect(snapshot.url).toMatch(/#ev4-anchor$/);
 });
});

test('[K:ten-viewport-geometry] real DOM responsive measurements',async({page})=>{
 const widths=JSON.parse(process.env.LAB_BREAKPOINTS||'[320,360,375,390,412,414,768,1024,1440,1920]');
 const observation=await observe('K:ten-viewport-geometry',async()=>{
  const records=[];
  for(const width of widths){
   await page.setViewportSize({width,height:900});
   await page.goto(frontend);
   const measurement=await page.locator('h2.e-heading-base').first().evaluate(node=>{
    const r=node.getBoundingClientRect();
    return {x:r.x,right:r.right,height:r.height,
     viewport:window.innerWidth,documentWidth:document.documentElement.scrollWidth};
   });
   records.push({width,...measurement});
  }
  return records;
 });
 fs.mkdirSync('./artifacts',{recursive:true});
 fs.writeFileSync('./artifacts/responsive-geometry.json',JSON.stringify(observation,null,2));
 await productAssertion('K:ten-viewport-geometry',observation,snapshot=>{
  expect(snapshot).toHaveLength(10);
  expect(snapshot[0].width).toBe(320);
  expect(snapshot[1].width).toBe(360);
  expect(snapshot[2].width).toBe(375);
  expect(snapshot[3].width).toBe(390);
  expect(snapshot[4].width).toBe(412);
  expect(snapshot[5].width).toBe(414);
  expect(snapshot[6].width).toBe(768);
  expect(snapshot[7].width).toBe(1024);
  expect(snapshot[8].width).toBe(1440);
  expect(snapshot[9].width).toBe(1920);
  for(const measurement of snapshot){
   expect(measurement.viewport).toBe(measurement.width);
   expect(measurement.height).toBeGreaterThan(0);
   expect(measurement.x).toBeGreaterThanOrEqual(-1);
   expect(measurement.right).toBeLessThanOrEqual(measurement.width+1);
   expect(measurement.documentWidth).toBeLessThanOrEqual(measurement.width+1);
  }
 });
});

test('[L:semantic-heading-name] accessible name and heading element',async({page})=>{
 const observation=await observe('L:semantic-heading-name',async()=>{
  await page.goto(frontend);
  const heading=page.getByRole('heading',{name:title,level:2});
  await settledCount(heading,1);
  const count=await heading.count();
  return {count,tag:count?await heading.first().evaluate(n=>n.tagName):null,
   name:count?await heading.first().textContent():null};
 });
 await productAssertion('L:semantic-heading-name',observation,snapshot=>{
  expect(snapshot.count).toBe(1);
  expect(snapshot.tag).toBe('H2');
  expect(snapshot.name).toBe('EV4 Atomic Heading');
 });
});

test('[N:atomic-and-legacy-coexist] two generations render on one page',async({page})=>{
 const observation=await observe('N:atomic-and-legacy-coexist',async()=>{
  await page.goto(frontend);
  const atomic=page.locator('h2.e-heading-base').first();
  const legacy=page.locator('.elementor-widget-heading .elementor-heading-title').first();
  await settledCount(page.locator('h2.e-heading-base'),1);
  const count=await atomic.count();
  return {atomicCount:count,atomicText:count?await atomic.textContent():null,
   legacyVisible:await legacy.isVisible()};
 });
 await productAssertion('N:atomic-and-legacy-coexist',observation,snapshot=>{
  expect(snapshot.atomicCount).toBe(1);
  expect(snapshot.atomicText).toBe('EV4 Atomic Heading');
  expect(snapshot.legacyVisible).toBe(true);
 });
});


test('[A:native-duplicate-delete] native Atomic duplicate and delete in real editor',async({page})=>{
 const ids=JSON.parse(fs.readFileSync('./artifacts/element-ids.json','utf8'));
 const observation=await observe('A:native-duplicate-delete',async()=>{
  await page.goto('/wp-login.php');
  await page.locator('#user_login').fill(process.env.LAB_ADMIN_USER||'admin');
  await page.locator('#user_pass').fill(process.env.LAB_ADMIN_PASS||'password');
  await page.locator('#wp-submit').click();
  await expect(page).toHaveURL(/\/wp-admin\//);
  await page.goto('/wp-admin/post.php?post='+postId+'&action=elementor');
  const frame=page.frameLocator('#elementor-preview-iframe');
  const headings=frame.locator('h2.e-heading-base');
  const before=await settledCount(headings,1);
  const duplicated=await page.evaluate(id=>{
   const container=window.elementor?.getContainer(id);
   if(!container||!window.$e?.run)throw new Error('Elementor editor command unavailable');
   const result=window.$e.run('document/elements/duplicate',{container});
   if(!result?.id)throw new Error('Duplicate command returned no native element');
   return result.id;
  },ids.atomic);
  const afterDuplicate=await settledCount(headings,2);
  await page.evaluate(id=>{
   const container=window.elementor.getContainer(id);
   if(!container)throw new Error('Duplicated editor container not found for deletion');
   window.$e.run('document/elements/delete',{container});
  },duplicated);
  const afterDelete=await settledCount(headings,1);
  return {before,afterDuplicate,afterDelete,
   finalText:afterDelete?await headings.first().textContent():null,expected:title};
 });
 await productAssertion('A:native-duplicate-delete',observation,snapshot=>{
  expect(snapshot.before).toBe(1);
  expect(snapshot.afterDuplicate).toBe(2);
  expect(snapshot.afterDelete).toBe(1);
  expect(snapshot.finalText).toBe(snapshot.expected);
 });
});

test('[I:keyboard-native-link] native Elementor button works through keyboard',async({page})=>{
 await page.goto(frontend);
 const link=page.locator('.elementor-button-link[href="#ev4-anchor"]').first();
 await expect(link).toBeVisible();
 await link.focus();
 await expect(link).toBeFocused();
 await page.keyboard.press('Enter');
 const observation=await observe('I:keyboard-native-link',async()=>{
  return {url:page.url(),focused:await link.evaluate(node=>document.activeElement===node)};
 });
 await productAssertion('I:keyboard-native-link',observation,snapshot=>{
  expect(snapshot.url).toMatch(/#ev4-anchor$/);
  expect(snapshot.focused).toBe(true);
 });
});


test('[L:keyboard-tab-reachability] the native Elementor link is reachable with Tab',async({page})=>{
 await page.goto(frontend);
 const link=page.locator('.elementor-button-link[href="#ev4-anchor"]').first();
 await expect(link).toBeVisible();
 let reached=false;
 for(let index=0;index<80;index++){
   await page.keyboard.press('Tab');
   if(await link.evaluate(node=>document.activeElement===node)){
     reached=true;
     break;
   }
 }
 const observation=await observe('L:keyboard-tab-reachability',async()=>({reached}));
 await productAssertion('L:keyboard-tab-reachability',observation,snapshot=>{
  expect(snapshot.reached,'Tab must reach the link without scripting focus').toBe(true);
 });
});

test('[L:contrast-aa-default-button] default Elementor button meets WCAG AA text contrast',async({page})=>{
 await page.goto(frontend);
 const link=page.locator('.elementor-button-link[href="#ev4-anchor"]').first();
 await expect(link).toBeVisible();
 const colors=await link.evaluate(node=>{
   const foreground=getComputedStyle(node).color;
   let ancestor=node;
   let background='rgba(0, 0, 0, 0)';
   while(ancestor){
     background=getComputedStyle(ancestor).backgroundColor;
     if(!['rgba(0, 0, 0, 0)','transparent'].includes(background))break;
     ancestor=ancestor.parentElement;
   }
   return {foreground,background};
 });
 function luminance(value){
   const match=/^rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/.exec(value);
   if(!match)throw new Error('Computed CSS color is not measurable: '+value);
   const channels=match.slice(1).map(Number).map(x=>{
     const scaled=x/255;
     return scaled<=0.04045?scaled/12.92:((scaled+0.055)/1.055)**2.4;
   });
   return channels[0]*0.2126+channels[1]*0.7152+channels[2]*0.0722;
 }
 const fg=luminance(colors.foreground);
 const bg=luminance(colors.background);
 const contrast=(Math.max(fg,bg)+0.05)/(Math.min(fg,bg)+0.05);
 fs.mkdirSync('./artifacts',{recursive:true});
 fs.writeFileSync('./artifacts/accessibility-contrast.json',JSON.stringify({...colors,contrast},null,2));
 const observation=await observe('L:contrast-aa-default-button',async()=>({contrast,...colors}));
 await productAssertion('L:contrast-aa-default-button',observation,snapshot=>{
  expect(snapshot.contrast,'Measured WCAG AA normal-text contrast').toBeGreaterThanOrEqual(4.5);
 });
});


test('[E:native-global-class-persistence] attach a real V4 global class and verify publication',async({page})=>{
 const ids=JSON.parse(fs.readFileSync('./artifacts/element-ids.json','utf8'));
 await page.goto('/wp-login.php');
 await page.locator('#user_login').fill(process.env.LAB_ADMIN_USER||'admin');
 await page.locator('#user_pass').fill(process.env.LAB_ADMIN_PASS||'password');
 await page.locator('#wp-submit').click();
 await expect(page).toHaveURL(/\/wp-admin\//);
 await page.goto('/wp-admin/post.php?post='+postId+'&action=elementor');
 const frame=page.frameLocator('#elementor-preview-iframe');
 await expect(frame.locator('[data-id="'+ids.atomic+'"]')).toBeVisible({timeout:60000});
 await page.evaluate(id=>{
   const container=window.elementor?.getContainer(id);
   if(!container||!window.$e?.run)throw new Error('Native editor selection interface absent');
   window.$e.run('document/elements/select',{container});
 },ids.atomic);
 const style=page.locator('[id^="tab-"][id$="-style"]');
 await expect(style).toBeVisible();
 await style.click();
 const input=page.locator('label',{hasText:'Classes'}).locator('../..').locator('input');
 await expect(input).toBeVisible();
 await input.fill('ev4-lab-shared');
 await page.keyboard.press('Enter');
 await expect(page.locator('[aria-label="Edit ev4-lab-shared"]')).toBeVisible();
 const save=page.getByRole('button',{name:/^Publish$/i}).first();
 await expect(save).toBeEnabled();
 await save.click();
 await expect(save).toBeDisabled({timeout:30000});
 await page.goto(frontend);
 const observation=await observe('E:native-global-class-persistence',async()=>{
  const heading=page.locator('h2.e-heading-base').first();
  await settledCount(page.locator('h2.e-heading-base'),1);
  return {count:await heading.count(),className:await heading.getAttribute('class')};
 });
 await productAssertion('E:native-global-class-persistence',observation,snapshot=>{
  expect(snapshot.count).toBe(1);
  expect(snapshot.className).toMatch(/ev4-lab-shared/);
 });
});
