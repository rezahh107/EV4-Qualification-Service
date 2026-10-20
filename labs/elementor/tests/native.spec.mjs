import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import { createAtomicFixture } from './helpers.mjs';

const postId = process.env.LAB_PAGE_ID;
const title = 'EV4 Atomic Heading';
const frontend = '/?page_id=' + postId;

test('[O:installed-runtime-browser] real WordPress HTTP form responds',async({page})=>{
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
