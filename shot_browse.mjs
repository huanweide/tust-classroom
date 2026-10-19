/** 截取三层导航各层级 + 深链直达的真实界面图（自带服务，零外部依赖） */
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const STATIC = fileURLToPath(new URL('./static/', import.meta.url));
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript',
  '.json': 'application/json; charset=utf-8', '.css': 'text/css',
  '.png': 'image/png', '.svg': 'image/svg+xml',
};
const server = createServer(async (req, res) => {
  try {
    const urlPath = decodeURIComponent(req.url.split('?')[0]);
    let fp = join(STATIC, normalize(urlPath));
    if (!existsSync(fp) || extname(fp) === '') fp = join(STATIC, 'index.html');
    const buf = await readFile(fp);
    res.writeHead(200, { 'Content-Type': MIME[extname(fp)] || 'application/octet-stream' });
    res.end(buf);
  } catch { res.writeHead(404); res.end('nf'); }
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${server.address().port}`;
console.log('服务 →', BASE);

const { chromium } = await import(
  'file:///C:/Users/Administrator/.workbuddy/binaries/node/workspace/node_modules/playwright/index.mjs'
);
const browser = await chromium.launch({
  executablePath: 'C:/Users/Administrator/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe',
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });

await page.goto(BASE + '/index.html', { waitUntil: 'networkidle' });
await page.waitForSelector('#panel-browse .bld-tile', { timeout: 20000 });
await page.waitForTimeout(400);
await page.screenshot({ path: 'shot-1-buildings.png', fullPage: true });

await page.locator('#panel-browse .bld-tile').first().click();
await page.waitForSelector('#panel-browse .room-tile', { timeout: 10000 });
await page.waitForTimeout(300);
await page.screenshot({ path: 'shot-2-rooms.png', fullPage: true });

// 第 3 层走深链（同时验证深链可用）
await page.goto(BASE + '/index.html?room=9-16', { waitUntil: 'networkidle' });
await page.waitForSelector('#panel-browse .tl-cell', { timeout: 15000 });
await page.waitForTimeout(400);
await page.screenshot({ path: 'shot-3-slots.png', fullPage: true });

await page.goto(BASE + '/index.html', { waitUntil: 'networkidle' });
await page.waitForSelector('#panel-browse .bld-tile', { timeout: 20000 });
await page.fill('#inp-global', '9-16');
await page.waitForTimeout(600);
await page.screenshot({ path: 'shot-4-search.png', fullPage: true });

await browser.close();
server.close();
console.log('4 张截图已生成');