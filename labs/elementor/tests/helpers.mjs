import { expect } from '@playwright/test';

export async function createAtomicFixture(page, postId) {
  await page.goto('/wp-login.php');
  await page.locator('#user_login').fill(process.env.LAB_ADMIN_USER || 'admin');
  await page.locator('#user_pass').fill(process.env.LAB_ADMIN_PASS || 'password');
  await page.locator('#wp-submit').click();
  await expect(page).toHaveURL(/\/wp-admin\//);
  await page.goto('/wp-admin/post.php?post=' + postId + '&action=elementor');
  await expect(page.locator('#elementor-preview-iframe')).toBeAttached({timeout:60000});
  const root = page.locator('#elementor-editor-wrapper-v2');
  await expect(root).toBeVisible({timeout:60000});
  await page.locator('.elementor-panel-loading').waitFor({state:'detached'});
  const ids = await page.evaluate(() => {
    if (!window.$e?.run || !window.elementor?.getContainer) {
      throw new Error('The running Elementor editor API is unavailable');
    }
    const create = (model, container) => window.$e.run('document/elements/create', {model,container});
    const container = create({elType:'container'}, window.elementor.getContainer('document'));
    const atomic = create({elType:'widget', widgetType:'e-heading'},container);
    const legacy = create({elType:'widget', widgetType:'heading',
      settings:{title:'Legacy companion'}},container);
    const button = create({elType:'widget', widgetType:'button',
      settings:{text:'Anchor link',link:{url:'#ev4-anchor'}}},container);
    if (!container?.id || !atomic?.id || !legacy?.id || !button?.id) {
      throw new Error('Elementor did not return native element IDs');
    }
    return {container:container.id,atomic:atomic.id,legacy:legacy.id,button:button.id};
  });
  return {root,ids};
}
