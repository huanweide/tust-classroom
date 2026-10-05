const puppeteer = require('puppeteer-core');
const fs = require('fs');

const CHROME = 'C:/Users/Administrator/.cache/puppeteer/chrome/win64-148.0.7778.167/chrome-win64/chrome.exe';
const URL = 'http://127.0.0.1:8123/index.html';
const SHOTS = 'C:/Users/Administrator/Documents/tust-classroom/e2e_shots';
fs.mkdirSync(SHOTS, { recursive: true });

const results = [];
const rec = (name, pass, detail) => {
  results.push({ name, pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${name} | ${detail}`);
};
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 414, height: 896 });
  const jsErrors = [];
  page.on('pageerror', e => jsErrors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') jsErrors.push(m.text()); });

  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  // 等 init 完成：校区下拉已填充并选中
  await page.waitForFunction(() => {
    const e = document.getElementById('sel-campus');
    return e && e.options.length > 0 && e.value;
  }, { timeout: 20000 });
  await sleep(500);

  // T1 默认校区
  const campus = await page.$eval('#sel-campus', e => e.value);
  rec('T1 默认校区=泰达', campus === '泰达', `实际=${campus}`);
  await page.screenshot({ path: `${SHOTS}/01_initial.png` });

  // T2 模式1：按节次查空闲
  await page.select('#sel-period', '1');
  await page.click('button[onclick="queryFreeRooms()"]');
  await sleep(900);
  const r2html = await page.$eval('#results', e => e.innerHTML);
  const r2txt = await page.$eval('#results', e => e.textContent);
  const t2ok = /result-card/.test(r2html) && !/请选择日期/.test(r2txt);
  rec('T2 按节次查空闲有结果', t2ok, r2txt.slice(0, 36).replace(/\s+/g, ' '));
  await page.screenshot({ path: `${SHOTS}/02_room.png` });

  // T3 模式2：时间范围查空闲
  await page.click('#btn-range');
  await sleep(250);
  const rangeActive = await page.$eval('#btn-range', e => e.classList.contains('active'));
  rec('T3a 切换到时间范围模式', rangeActive, `btn-range.active=${rangeActive}`);
  const ends = await page.$$eval('#sel-end option', os => os.map(o => o.value));
  await page.select('#sel-start', '1');
  await page.select('#sel-end', ends[ends.length - 1]);
  await page.click('button[onclick="queryFreeRange()"]');
  await sleep(900);
  const r3txt = await page.$eval('#results', e => e.textContent);
  rec('T3b 时间范围查询有结果', !/请选择日期/.test(r3txt) && r3txt.trim().length > 3, r3txt.slice(0, 36).replace(/\s+/g, ' '));
  await page.screenshot({ path: `${SHOTS}/03_range.png` });

  // T4 模式3：查教室时段 9-3
  await page.click('#btn-classroom');
  await sleep(250);
  await page.$eval('#inp-classroom', (el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); }, '9-3');
  await page.click('button[onclick="queryClassroomSlots()"]');
  await sleep(900);
  const r4 = await page.$eval('#results', e => e.textContent);
  rec('T4 查教室 9-3 → 3阶梯(d)', /3阶梯/.test(r4), r4.slice(0, 48).replace(/\s+/g, ' '));
  await page.screenshot({ path: `${SHOTS}/04_classroom_9-3.png` });

  // T5 模式3：3阶梯
  await page.$eval('#inp-classroom', (el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); }, '3阶梯');
  await page.click('button[onclick="queryClassroomSlots()"]');
  await sleep(900);
  const r5 = await page.$eval('#results', e => e.textContent);
  rec('T5 查教室 3阶梯 → 3阶梯(d)', /3阶梯/.test(r5), r5.slice(0, 48).replace(/\s+/g, ' '));

  // T6 校区切换 → 河西
  await page.select('#sel-campus', '河西');
  await sleep(500);
  const bldOpts = await page.$$eval('#sel-building-room option', os => os.map(o => o.textContent));
  const hasJieti = bldOpts.some(t => t.includes('阶梯'));
  rec('T6 切河西→教学楼含"阶梯"楼', hasJieti, `楼栋数=${bldOpts.length}`);
  await page.screenshot({ path: `${SHOTS}/05_hexibuildings.png` });

  // T7 教学楼过滤（河西选 阶梯 楼）
  if (hasJieti) {
    const jt = bldOpts.find(t => t.includes('阶梯'));
    await page.select('#sel-building-room', jt);
    await page.click('#btn-room');
    await sleep(250);
    await page.click('button[onclick="queryFreeRooms()"]');
    await sleep(900);
    const r7 = await page.$eval('#results', e => e.textContent);
    rec('T7 教学楼过滤生效', !/请选择日期/.test(r7) && r7.trim().length > 3, `楼=${jt} ${r7.slice(0, 28).replace(/\s+/g, ' ')}`);
  }

  // T8 日期后一天导航
  const before = await page.$eval('#date-scroll .date-chip.active', e => e.dataset.date).catch(() => null);
  await page.click('button[onclick="shiftDate(1)"]');
  await sleep(400);
  const after = await page.$eval('#date-scroll .date-chip.active', e => e.dataset.date).catch(() => null);
  rec('T8 日期后一天导航', !!(before && after && before !== after), `before=${before} after=${after}`);

  // T9 搜索自动补全（切回泰达，搜"阶梯"——泰达教室名含"阶梯"）
  await page.select('#sel-campus', '泰达');
  await sleep(400);
  await page.click('#btn-classroom');
  await sleep(250);
  await page.$eval('#inp-classroom', (el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); }, '阶梯');
  await sleep(1200);
  const sugCount = await page.$$eval('#classroom-suggestions option', os => os.length);
  rec('T9 搜索自动补全有建议', sugCount > 0, `建议数=${sugCount}`);

  const realErrs = jsErrors.filter(e => !/MIME type|serviceWorker|sw\.js/i.test(e));
  rec('T10 页面无JS错误(忽略本地sw MIME)', realErrs.length === 0, realErrs.slice(0, 2).join(' | '));

  await browser.close();
  const pass = results.filter(r => r.pass).length;
  console.log(`\n=== 端到端结果: ${pass}/${results.length} 通过 ===`);
  fs.writeFileSync('C:/Users/Administrator/Documents/tust-classroom/e2e_result.json', JSON.stringify(results, null, 2));
  process.exit(pass === results.length ? 0 : 1);
})().catch(e => { console.error('FATAL', e); process.exit(2); });
