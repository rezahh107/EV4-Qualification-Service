import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import { createAtomicFixture } from './helpers.mjs';

const postId = process.env.LAB_PAGE_ID;
const title = 'EV4 Atomic Heading';
const frontend = '/?page_id=' + postId;

test('[O:installed-runtime-browser] real WordPress HTTP form responds',async({page,browser})=>{
 fs.mkdirSync('./artifacts',{recursive:true});
 fs.writeFileSync('./artifacts/browser.json',JSON.stringify({engine:'chromium',version:browser.version()},null,2));
 const response=await page.goto('/wp-login.php');
 expect(response?.status()).toBe(200);
 await expect(page.locator('#user_login')).toBeVisible();
 await expect(page.locator('#user_pass')).toBeVisible();
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
 await page.goto(frontend);
 await expect(page.locator('h2.e-heading-base').first()).toHaveText(title);
 fs.mkdirSync('./artifacts',{recursive:true});
 fs.writeFileSync('./artifacts/element-ids.json',JSON.stringify(ids,null,2));
});

test('[A:native-parent-child] actual published V4 element retains parent',async({page})=>{
 await page.goto(frontend);
 const heading=page.locator('h2.e-heading-base').first();
 await expect(heading).toHaveText(title);
 const ids=JSON.parse(fs.readFileSync('./artifacts/element-ids.json','utf8'));
 const data=await heading.evaluate(node=>{
   const parent=node.closest('[data-element_type="container"]');
   return {atomicId:node.getAttribute('data-interaction-id'),
      parentId:parent?.getAttribute('data-id')};
 });
 expect(data).toEqual({atomicId:ids.atomic,parentId:ids.container});
});

test('[B:native-flex-container] native published flex layout is computed',async({page})=>{
 await page.goto(frontend);
 const display=await page.locator('.e-heading-base').first().evaluate(node=>{
   const container=node.closest('.e-con');
   return container ? getComputedStyle(container).display : null;
 });
 expect(display).toBe('flex');
});

test('[C:measured-geometry] published heading occupies nonzero bounds',async({page})=>{
 await page.goto(frontend);
 const rect=await page.locator('h2.e-heading-base').first().boundingBox();
 expect(rect).not.toBeNull();
 expect(rect.width).toBeGreaterThan(5);
 expect(rect.height).toBeGreaterThan(5);
});

test('[D:atomic-semantic-heading] atomic widget uses semantic H2',async({page})=>{
 await page.goto(frontend);
 await expect(page.getByRole('heading',{name:title,level:2})).toBeVisible();
 await expect(page.locator('h2.e-heading-base').first()).toHaveText(title);
});

test('[I:native-link-activation] native Elementor link activates anchor',async({page})=>{
 await page.goto(frontend);
 const link=page.locator('.elementor-button-link[href="#ev4-anchor"]').first();
 await expect(link).toBeVisible();
 await link.click();
 await expect(page).toHaveURL(/#ev4-anchor$/);
});

test('[K:ten-viewport-geometry] real DOM responsive measurements',async({page})=>{
 const widths=JSON.parse(process.env.LAB_BREAKPOINTS||'[320,360,375,390,412,414,768,1024,1440,1920]');
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
   expect(measurement.height).toBeGreaterThan(0);
   expect(measurement.x).toBeGreaterThanOrEqual(-1);
   expect(measurement.right).toBeLessThanOrEqual(width+1);
   expect(measurement.documentWidth).toBeLessThanOrEqual(width+1);
 }
 fs.mkdirSync('./artifacts',{recursive:true});
 fs.writeFileSync('./artifacts/responsive-geometry.json',JSON.stringify(records,null,2));
});

test('[L:semantic-heading-name] accessible name and heading element',async({page})=>{
 await page.goto(frontend);
 const heading=page.getByRole('heading',{name:title,level:2});
 await expect(heading).toBeVisible();
 const info=await heading.evaluate(n=>({tag:n.tagName,name:n.textContent.trim()}));
 expect(info).toEqual({tag:'H2',name:title});
});

test('[N:atomic-and-legacy-coexist] two generations render on one page',async({page})=>{
 await page.goto(frontend);
 await expect(page.locator('h2.e-heading-base').first()).toHaveText(title);
 await expect(page.locator('.elementor-widget-heading .elementor-heading-title').first()).toBeVisible();
});


test('[A:native-duplicate-delete] native Atomic duplicate and delete in real editor',async({page})=>{
 const ids=JSON.parse(fs.readFileSync('./artifacts/element-ids.json','utf8'));
 await page.goto('/wp-login.php');
 await page.locator('#user_login').fill(process.env.LAB_ADMIN_USER||'admin');
 await page.locator('#user_pass').fill(process.env.LAB_ADMIN_PASS||'password');
 await page.locator('#wp-submit').click();
 await expect(page).toHaveURL(/\/wp-admin\//);
 await page.goto('/wp-admin/post.php?post='+postId+'&action=elementor');
 const frame=page.frameLocator('#elementor-preview-iframe');
 const headings=frame.locator('h2.e-heading-base');
 await expect(headings).toHaveCount(1,{timeout:60000});
 const duplicated=await page.evaluate(id=>{
   const container=window.elementor?.getContainer(id);
   if(!container||!window.$e?.run)throw new Error('Elementor editor command unavailable');
   const result=window.$e.run('document/elements/duplicate',{container});
   if(!result?.id)throw new Error('Duplicate command returned no native element');
   return result.id;
 },ids.atomic);
 await expect(headings).toHaveCount(2);
 await page.evaluate(id=>{
   const container=window.elementor.getContainer(id);
   if(!container)throw new Error('Duplicated editor container not found for deletion');
   window.$e.run('document/elements/delete',{container});
 },duplicated);
 await expect(headings).toHaveCount(1);
 await expect(headings).toContainText([title]);
});

test('[I:keyboard-native-link] native Elementor button works through keyboard',async({page})=>{
 await page.goto(frontend);
 const link=page.locator('.elementor-button-link[href="#ev4-anchor"]').first();
 await expect(link).toBeVisible();
 await link.focus();
 await expect(link).toBeFocused();
 await page.keyboard.press('Enter');
 await expect(page).toHaveURL(/#ev4-anchor$/);
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
 expect(reached,'Tab must reach the link without scripting focus').toBe(true);
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
 expect(contrast,'Measured WCAG AA normal-text contrast').toBeGreaterThanOrEqual(4.5);
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
 await expect(page.locator('h2.e-heading-base').first()).toHaveClass(/ev4-lab-shared/);
});
