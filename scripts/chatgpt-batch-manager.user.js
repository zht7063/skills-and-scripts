// ==UserScript==
// @name         ChatGPT 会话批量管理（归档 / 删除）
// @namespace    local.chatgpt.batch-manager
// @version      1.0.5
// @description  在 ChatGPT 侧栏添加复选框，批量归档或删除选中的会话；确认、串行执行、停止及逐条结果。
// @match        https://chatgpt.com/*
// @run-at       document-idle
// @grant        none
// @noframes
// @license      MIT
// ==/UserScript==

/*
 * 安装：Tampermonkey → 添加新脚本 → 用本文件全部内容替换模板 → 保存 → 刷新 ChatGPT。
 * 范围：只识别侧栏已经加载的普通会话链接；向下滚动侧栏可加载更多。
 * “全选已加载”不是“选择账号全部历史”。不会主动拉取全部历史或消息正文。
 * 归档可以从设置中的已归档聊天恢复；删除无法恢复。
 * 使用当前登录态；不需要 API Key，不向第三方发送数据，不持久保存令牌。
 * 本版本按个人账号使用，不读取工作区信息或附加工作区请求头。
 * 管理面板固定在会话侧栏底部，每次加载默认收起，点击标题栏展开。
 * 依赖未公开承诺稳定的网页接口与 DOM，改版后可能需要调整。
 * 开发验证使用模拟网页/响应；没有用你的真实会话执行删除测试。
 *
 * 兼容性依据（接口形状参考，以下链接不会由脚本请求）：
 * https://github.com/pionxzh/chatgpt-exporter/blob/master/src/api.ts
 * https://github.com/learnerLj/ai-chat-bulk-manager/blob/master/spec.md
 * https://help.openai.com/en/articles/8809935-deleting-and-archiving-chats-in-chatgpt
 */

(() => {
  'use strict';
  if (location.origin !== 'https://chatgpt.com' || window.top !== window.self) return;
  if (document.getElementById('cgbm-style')) return;

  const PREFIX = 'cgbm';
  const TIMEOUT_MS = 20000;
  const GAP_MS = 700;
  const UUID = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
  const CHAT_PATH = new RegExp(`^/(?:g/[^/]+/)?c/(${UUID})/?$`, 'i');
  const SCOPES = '#history, [data-testid="history"], [data-testid="sidebar"], [data-testid="sidebar-panel"], #stage-slideover-sidebar, aside, nav, [role="navigation"]';
  const HISTORY_SCOPES = '#history, [data-testid="history"], [data-testid="history-links"]';
  const EXCLUDE = 'main, [role="main"], [data-message-author-role], [contenteditable="true"]';
  const ROW_BOUNDARIES = `${SCOPES}, ${HISTORY_SCOPES}, ul, ol, [role="list"], [role="group"], [role="menu"]`;
  const ROW_HEADINGS = 'h1, h2, h3, h4, h5, h6, [role="heading"], hr, [role="separator"]';
  const selected = new Map();
  const completed = new Set();
  const records = new Map();
  const parents = new Map();
  let loaded = new Map();
  let phase = 'idle';
  let stopRequested = false;
  let refreshRequired = false;
  let scheduleId = 0;
  let lastMessage = '';
  let collapsed = true;
  let dockRoot = null;
  let spacerLayoutKey = '';
  let dockWatchRoot = null;
  let dockWatchNodes = new Set();

  const css = `
    .cgbm-ui {
      --cgbm-bg:#ffffff; --cgbm-fg:#202123; --cgbm-muted:#646464;
      --cgbm-border:#d9d9d9; --cgbm-accent:#087f5b; --cgbm-danger:#b42318;
      --cgbm-hover:#f1f3f2; --cgbm-selected:#e6f5ef; --cgbm-scrim:rgb(0 0 0 / .45);
      --cgbm-font:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
      --cgbm-radius:8px; --cgbm-panel-radius:12px;
      font-family:var(--cgbm-font); font-size:13px; line-height:1.5;
      color:var(--cgbm-fg); color-scheme:light; box-sizing:border-box;
    }
    .dark .cgbm-ui, [data-theme="dark"] .cgbm-ui {
      --cgbm-bg:#202123; --cgbm-fg:#ececec; --cgbm-muted:#b4b4b4;
      --cgbm-border:#565656; --cgbm-accent:#75d5b0; --cgbm-danger:#ffb4ab;
      --cgbm-hover:#303433; --cgbm-selected:#234337; color-scheme:dark;
    }
    @media (prefers-color-scheme:dark) {
      html:not(.light):not([data-theme="light"]) .cgbm-ui {
        --cgbm-bg:#202123; --cgbm-fg:#ececec; --cgbm-muted:#b4b4b4;
        --cgbm-border:#565656; --cgbm-accent:#75d5b0; --cgbm-danger:#ffb4ab;
        --cgbm-hover:#303433; --cgbm-selected:#234337; color-scheme:dark;
      }
    }
    .cgbm-ui *, .cgbm-ui *::before, .cgbm-ui *::after { box-sizing:border-box; }
    /* Override both host styles and this script's flex display for hidden controls. */
    .cgbm-ui[hidden], .cgbm-ui [hidden] { display:none !important; }
    .cgbm-ui, .cgbm-ui * { scrollbar-width:thin; scrollbar-color:var(--cgbm-muted) var(--cgbm-bg); }
    .cgbm-ui ::-webkit-scrollbar { width:8px; height:8px; }
    .cgbm-ui ::-webkit-scrollbar-track { background:var(--cgbm-bg); }
    .cgbm-ui ::-webkit-scrollbar-thumb { background:var(--cgbm-muted); border-radius:8px; border:2px solid var(--cgbm-bg); }
    .cgbm-ui ::-webkit-scrollbar-thumb:hover, .cgbm-ui ::-webkit-scrollbar-thumb:active { background:var(--cgbm-fg); }
    #cgbm-panel {
      background:var(--cgbm-bg); border:1px solid var(--cgbm-border);
      border-radius:var(--cgbm-panel-radius); margin:0; padding:10px;
      width:min(280px,calc(100vw - 24px)); min-width:0; position:fixed; z-index:50;
      max-height:calc(100dvh - 24px);
      display:flex; flex-direction:column;
    }
    .cgbm-body { min-height:0; overflow-y:auto; overscroll-behavior:contain; }
    .cgbm-spacer { display:block; width:1px; flex:0 0 auto; visibility:hidden; pointer-events:none; }
    .cgbm-header, .cgbm-select-line, .cgbm-actions, .cgbm-footer { display:flex; align-items:center; gap:8px; }
    .cgbm-header { justify-content:space-between; }
    .cgbm-header strong { font-size:14px; font-weight:650; min-width:0; overflow:hidden; text-overflow:ellipsis; }
    .cgbm-count { color:var(--cgbm-muted); font-size:12px; font-variant-numeric:tabular-nums; flex:none; }
    .cgbm-chevron { flex:none; width:12px; text-align:center; color:var(--cgbm-muted); }
    .cgbm-select-line { justify-content:space-between; margin:8px 0; flex-wrap:wrap; }
    .cgbm-ui label { display:inline-flex; align-items:center; gap:6px; cursor:pointer; }
    .cgbm-ui input[type="checkbox"] { appearance:auto; width:17px; height:17px; margin:0; accent-color:var(--cgbm-accent); cursor:pointer; flex:none; }
    .cgbm-ui input:disabled { cursor:default; }
    .cgbm-ui button {
      appearance:none; border:1px solid var(--cgbm-border); border-radius:var(--cgbm-radius);
      padding:6px 9px; margin:0; background:var(--cgbm-bg); color:var(--cgbm-fg);
      font:inherit; font-weight:550; line-height:1.4; min-height:32px; cursor:pointer; white-space:nowrap;
    }
    .cgbm-ui button:hover:not(:disabled) { background:var(--cgbm-hover); }
    .cgbm-ui button:active:not(:disabled) { transform:translateY(1px); }
    .cgbm-ui button:disabled { opacity:.5; cursor:default; }
    .cgbm-ui button:focus-visible, .cgbm-ui input:focus-visible, .cgbm-ui summary:focus-visible { outline:2px solid var(--cgbm-accent); outline-offset:3px; }
    .cgbm-ui button.cgbm-danger { color:var(--cgbm-danger); border-color:var(--cgbm-danger); }
    .cgbm-ui button.cgbm-commit { background:var(--cgbm-danger); color:var(--cgbm-bg); }
    .cgbm-ui button.cgbm-commit:hover:not(:disabled) { filter:brightness(.9); background:var(--cgbm-danger); }
    .cgbm-ui button.cgbm-text { border-color:transparent; padding:2px 4px; min-height:26px; font-size:12px; color:var(--cgbm-muted); }
    #cgbm-panel > .cgbm-header {
      width:100%; padding:0; border:0; min-height:24px; flex:none; gap:6px;
      background:transparent; text-align:start;
    }
    #cgbm-panel > .cgbm-header:hover { background:var(--cgbm-hover); }
    .cgbm-actions > button { flex:1; min-width:0; }
    .cgbm-footer { margin-top:8px; flex-wrap:wrap; }
    .cgbm-status { color:var(--cgbm-muted); min-height:36px; margin:8px 0 0; font-size:12px; overflow-wrap:anywhere; }
    .cgbm-status[data-tone="error"] { color:var(--cgbm-danger); }
    .cgbm-ui progress { display:block; width:100%; height:5px; margin-top:8px; accent-color:var(--cgbm-accent); }
    .cgbm-ui details { margin-top:6px; font-size:12px; }
    .cgbm-ui summary { cursor:pointer; color:var(--cgbm-muted); }
    .cgbm-ui summary:hover { color:var(--cgbm-fg); }
    .cgbm-log { margin:6px 0 0; padding:0 0 0 18px; max-height:130px; overflow:auto; scrollbar-gutter:stable; overflow-wrap:anywhere; }
    .cgbm-log li { margin:0 0 5px; }
    .cgbm-check-wrap { position:absolute; z-index:4; width:26px; height:28px; display:flex; align-items:center; justify-content:center; padding:0; cursor:pointer; }
    /* Reserve checkbox space without deleting or reparenting React-owned links. */
    .cgbm-link { padding-inline-start:calc(var(--cgbm-original-padding,8px) + 32px) !important; }
    .cgbm-link[data-cgbm-selected="true"] { outline:1px solid currentColor; outline-offset:-2px; }
    .cgbm-done { display:none !important; }
    #cgbm-confirm {
      padding:22px; background:var(--cgbm-bg); color:var(--cgbm-fg); border:1px solid var(--cgbm-border);
      border-radius:var(--cgbm-panel-radius); width:min(540px,calc(100vw - 32px));
      max-height:calc(100dvh - 40px); overflow:auto; scrollbar-gutter:stable; margin:auto;
      box-shadow:0 12px 48px rgb(0 0 0 / .2);
    }
    #cgbm-confirm::backdrop { background:var(--cgbm-scrim); }
    #cgbm-confirm h2 { margin:0 0 8px; font-size:19px; font-weight:650; line-height:1.4; }
    #cgbm-confirm p { margin:8px 0; overflow-wrap:anywhere; }
    #cgbm-confirm .cgbm-confirm-list { max-height:min(280px,35dvh); overflow:auto; scrollbar-gutter:stable; padding-left:24px; margin:12px 0; }
    #cgbm-confirm li { margin:0 0 10px; overflow-wrap:anywhere; }
    #cgbm-confirm code { display:block; color:var(--cgbm-muted); font-family:ui-monospace,monospace; font-size:11px; word-break:break-all; }
    #cgbm-confirm .cgbm-actions { justify-content:flex-end; margin-top:16px; }
    #cgbm-confirm .cgbm-actions > button { flex:0 1 auto; white-space:normal; }
    @media (forced-colors:active) {
      .cgbm-ui, .cgbm-ui * { scrollbar-color:auto; }
      .cgbm-ui button, #cgbm-panel, #cgbm-confirm { border-color:ButtonText; }
      .cgbm-ui button.cgbm-commit { background:ButtonFace; color:ButtonText; }
    }
    @media (prefers-reduced-motion:reduce) { .cgbm-ui *, .cgbm-ui *::before, .cgbm-ui *::after { animation:none !important; transition:none !important; } }
  `;
  const style = document.createElement('style');
  style.id = `${PREFIX}-style`;
  style.textContent = css;
  (document.head || document.documentElement).append(style);

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function button(action, text, handler, className = '') {
    const node = el('button', className, text);
    node.type = 'button';
    node.dataset.cbmAction = action;
    node.addEventListener('click', handler);
    return node;
  }
  const panel = el('section', 'cgbm-ui');
  panel.id = 'cgbm-panel';
  panel.hidden = true;
  panel.setAttribute('aria-label', '会话批量管理');
  const heading = button('toggle', '', () => {
    collapsed = !collapsed;
    body.hidden = collapsed;
    heading.setAttribute('aria-expanded', String(!collapsed));
    heading.title = collapsed ? '展开会话批量管理' : '收起会话批量管理';
    chevron.textContent = collapsed ? '▸' : '▾';
    render();
    reposition();
  }, 'cgbm-header');
  heading.setAttribute('aria-expanded', 'false');
  heading.setAttribute('aria-controls', 'cgbm-body');
  heading.title = '展开会话批量管理';
  const counts = el('span', 'cgbm-count', '已选 0');
  const chevron = el('span', 'cgbm-chevron', '▸');
  chevron.setAttribute('aria-hidden', 'true');
  heading.append(el('strong', '', '会话批量管理'), counts, chevron);
  const body = el('div', 'cgbm-body');
  body.id = 'cgbm-body';
  body.hidden = true;
  const dockSpacer = el('div', 'cgbm-ui cgbm-spacer');
  dockSpacer.id = 'cgbm-panel-spacer';
  dockSpacer.setAttribute('aria-hidden', 'true');
  dockSpacer.hidden = true;
  const selectLine = el('div', 'cgbm-select-line');
  const selectLabel = el('label');
  const selectAll = el('input');
  selectAll.type = 'checkbox';
  selectAll.dataset.cbmAction = 'select-all';
  selectLabel.append(selectAll, el('span', '', '全选已加载'));
  const clear = button('clear', '清空选择', () => {
    if (phase !== 'idle') return;
    selected.clear(); render();
  }, 'cgbm-text');
  selectLine.append(selectLabel, clear);
  const actions = el('div', 'cgbm-actions');
  const archive = button('archive', '批量归档', () => void requestBatch('archive'));
  const remove = button('delete', '批量删除', () => void requestBatch('delete'), 'cgbm-danger');
  actions.append(archive, remove);
  const footer = el('div', 'cgbm-footer');
  const stop = button('stop', '停止后续操作', () => {
    if (phase !== 'running') return;
    stopRequested = true;
    setStatus('正在停止：等待当前请求结束，不再处理下一条。');
    render();
  });
  stop.hidden = true;
  const refresh = button('refresh', '刷新列表', () => {
    if (phase === 'idle') location.reload();
  }, 'cgbm-text');
  refresh.title = '会重载整个页面，请先保存尚未发送的草稿。';
  footer.append(stop, refresh);
  const status = el('p', 'cgbm-status');
  status.dataset.cbmStatus = '';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  status.setAttribute('aria-atomic', 'true');
  const progress = el('progress');
  progress.setAttribute('aria-label', '批量操作进度');
  progress.hidden = true;
  const details = el('details');
  const logSummary = el('summary', '', '操作结果');
  const log = el('ol', 'cgbm-log');
  details.append(logSummary, log); details.hidden = true;
  body.append(selectLine, actions, footer, progress, status, details);
  panel.append(heading, body);
  document.body.append(panel);

  function conversationId(anchor) {
    if (!(anchor instanceof HTMLAnchorElement)) return null;
    try {
      const url = new URL(anchor.getAttribute('href') || '', location.origin);
      if (url.origin !== location.origin) return null;
      return url.pathname.match(CHAT_PATH)?.[1].toLowerCase() || null;
    } catch { return null; }
  }
  function scopeOf(anchor) {
    if (anchor.closest(EXCLUDE)) return null;
    return anchor.closest(SCOPES);
  }
  function titleOf(anchor) {
    return (anchor.getAttribute('title') || anchor.getAttribute('aria-label') || anchor.textContent || '未命名会话').trim().replace(/\s+/g, ' ').slice(0, 500);
  }
  function visible(node) {
    if (!node.isConnected || !node.getClientRects().length) return false;
    const computed = getComputedStyle(node);
    return computed.display !== 'none' && computed.visibility !== 'hidden';
  }
  function setSelected(id, title, checked) {
    if (phase !== 'idle') return;
    if (checked) {
      selected.set(id, {id, title});
    } else {
      selected.delete(id);
    }
    render();
  }
  selectAll.addEventListener('change', () => {
    if (phase !== 'idle') { render(); return; }
    if (selectAll.checked) {
      for (const [id, item] of loaded) selected.set(id, {id, title:item.title});
    } else {
      for (const id of loaded.keys()) selected.delete(id);
    }
    render();
  });

  function attach(anchor, id) {
    const parent = anchor.parentElement;
    if (!parent) return null;
    if (!parents.has(parent)) {
      const oldPosition = parent.style.position;
      const changed = getComputedStyle(parent).position === 'static';
      if (changed) parent.style.position = 'relative';
      parents.set(parent, {count:0, oldPosition, changed});
    }
    parents.get(parent).count++;
    const originalPadding = getComputedStyle(anchor).paddingInlineStart;
    const oldPaddingVar = anchor.style.getPropertyValue('--cgbm-original-padding');
    anchor.style.setProperty('--cgbm-original-padding', originalPadding);
    anchor.classList.add('cgbm-link');
    const wrapper = el('label', 'cgbm-ui cgbm-check-wrap');
    const input = el('input', 'cgbm-checkbox');
    input.type = 'checkbox'; input.dataset.cbmCheckbox = id;
    wrapper.append(input);
    parent.insertBefore(wrapper, anchor);
    const record = {anchor, parent, wrapper, input, id, originalPadding, oldPaddingVar, hiddenRow:null};
    // The input is a sibling of the link; prevent site-level click delegation.
    for (const event of ['click', 'pointerdown', 'pointerup', 'mousedown', 'mouseup', 'keydown', 'keyup']) {
      wrapper.addEventListener(event, e => e.stopPropagation());
    }
    input.addEventListener('change', () => {
      if (conversationId(anchor) !== record.id || !scopeOf(anchor)) { scheduleScan(); return; }
      setSelected(record.id, titleOf(anchor), input.checked);
      render();
    });
    records.set(anchor, record);
    return record;
  }
  function detach(record) {
    record.wrapper.remove();
    record.anchor.classList.remove('cgbm-link', 'cgbm-done');
    record.anchor.removeAttribute('data-cgbm-selected');
    if (record.oldPaddingVar) record.anchor.style.setProperty('--cgbm-original-padding', record.oldPaddingVar);
    else record.anchor.style.removeProperty('--cgbm-original-padding');
    if (record.hiddenRow) record.hiddenRow.classList.remove('cgbm-done');
    const info = parents.get(record.parent);
    if (info && --info.count === 0) {
      if (info.changed && record.parent.style.position === 'relative') record.parent.style.position = info.oldPosition;
      parents.delete(record.parent);
    }
    records.delete(record.anchor);
  }
  function ownsConversationRow(node, anchor) {
    if (!node?.contains(anchor) || node.matches(`${ROW_BOUNDARIES}, ${ROW_HEADINGS}`) ||
        node.querySelector(`${ROW_BOUNDARIES}, ${ROW_HEADINGS}`)) return false;
    // A single conversation's row must not contain another chat or navigation link.
    const links = node.querySelectorAll('a[href]');
    if (links.length !== 1 || links[0] !== anchor) return false;
    return !/^(auto|scroll|overlay)$/.test(getComputedStyle(node).overflowY);
  }
  function conversationRow(record) {
    const {anchor, hiddenRow} = record;
    // Reuse the proven row: its geometry is zero after display:none.
    if (hiddenRow && ownsConversationRow(hiddenRow, anchor)) return hiddenRow;
    let row = null;
    const maxHeight = Math.max(96, anchor.getBoundingClientRect().height + 32);
    for (let node = anchor.parentElement; node && node !== document.body; node = node.parentElement) {
      if (!ownsConversationRow(node, anchor) || node.getBoundingClientRect().height > maxHeight) break;
      const explicitItem = node.matches('li, [role="listitem"], [data-testid^="history-item-"]');
      if (explicitItem || node.tagName === 'DIV') row = node;
      if (explicitItem) break;
    }
    return row;
  }
  function markDone(record) {
    // Find the whole row while it still has layout, including nested DIV wrappers.
    const row = conversationRow(record);
    if (record.hiddenRow && record.hiddenRow !== row) record.hiddenRow.classList.remove('cgbm-done');
    record.hiddenRow = row;
    record.wrapper.hidden = true;
    record.anchor.classList.add('cgbm-done');
    // Keep React-owned nodes in place; display:none also removes row spacing.
    if (row) row.classList.add('cgbm-done');
  }
  function position(record) {
    const {anchor, parent, wrapper} = record;
    if (!visible(anchor) || completed.has(record.id)) { wrapper.hidden = true; return; }
    wrapper.hidden = false;
    const a = anchor.getBoundingClientRect();
    const p = parent.getBoundingClientRect();
    const rtl = getComputedStyle(anchor).direction === 'rtl';
    const parsedInset = parseFloat(record.originalPadding);
    const inset = Number.isFinite(parsedInset) ? parsedInset : 8;
    const left = (rtl ? a.right - inset - 26 : a.left + inset) - p.left - parent.clientLeft + parent.scrollLeft;
    const top = a.top - p.top - parent.clientTop + parent.scrollTop + (a.height - 28) / 2;
    const x = `${Math.round(left)}px`, y = `${Math.round(top)}px`;
    if (wrapper.style.left !== x) wrapper.style.left = x;
    if (wrapper.style.top !== y) wrapper.style.top = y;
  }
  function dockRect(root) {
    if (!root?.isConnected || !visible(root) || root.closest(EXCLUDE)) return null;
    let left = 0, top = 0, right = document.documentElement.clientWidth, bottom = window.innerHeight;
    for (let node = root; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (node.hidden || node.inert || node.getAttribute('aria-hidden') === 'true' ||
          style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse' ||
          Number(style.opacity) === 0) return null;
      const rect = node.getBoundingClientRect();
      if (node === root || /^(auto|scroll|hidden|clip|overlay)$/.test(style.overflowX)) {
        left = Math.max(left, rect.left); right = Math.min(right, rect.right);
      }
      if (node === root || /^(auto|scroll|hidden|clip|overlay)$/.test(style.overflowY)) {
        top = Math.max(top, rect.top); bottom = Math.min(bottom, rect.bottom);
      }
    }
    return {left, right, top, bottom, width:right - left, height:bottom - top};
  }
  function containsHistory(root) {
    if (!root?.isConnected) return false;
    const regions = root.matches(HISTORY_SCOPES) ? [root] : [...root.querySelectorAll(HISTORY_SCOPES)];
    if (regions.some(region => {
      const rect = dockRect(region);
      return rect && rect.width > 0 && rect.height >= 0;
    })) return true;
    return [...root.querySelectorAll('a[href*="/c/"]')].some(anchor => {
      const id = conversationId(anchor);
      if (!id || !scopeOf(anchor)) return false;
      let witness = anchor;
      // Completed rows still establish history ownership; only our own hiding is ignored.
      if (completed.has(id)) {
        let hidden;
        while (witness && (hidden = witness.closest('.cgbm-done'))) witness = hidden.parentElement;
      }
      if (!witness || !root.contains(witness)) return false;
      const rect = dockRect(witness);
      return rect && rect.width > 0;
    });
  }
  function historyDock(source, scope) {
    let root = source?.closest('nav, [role="navigation"]') || scope;
    // Dock to the history's bounded scroll area, above any separate account footer.
    // Keep the panel outside React-owned nodes; a spacer preserves the final row.
    for (let node = source; node && node !== document.body; node = node.parentElement) {
      const rect = node.getBoundingClientRect();
      if (rect.width >= 170 && rect.width <= 480 && rect.height >= 80 &&
          /^(auto|scroll|overlay)$/.test(getComputedStyle(node).overflowY)) {
        root = node;
        break;
      }
    }
    return root;
  }
  function watchDock(root) {
    if (root) dockWatchRoot = root;
    if (!dockWatchRoot?.isConnected) dockWatchRoot = null;
    const nodes = new Set();
    const addBranch = node => { for (; node; node = node.parentElement) nodes.add(node); };
    addBranch(dockWatchRoot || document.body);
    if (dockWatchRoot) for (const region of dockWatchRoot.querySelectorAll(HISTORY_SCOPES)) addBranch(region);
    if (nodes.size === dockWatchNodes.size && [...nodes].every(node => dockWatchNodes.has(node))) return;
    dockWatchNodes = nodes;
    dockAttributeObserver.disconnect();
    for (const node of nodes) dockAttributeObserver.observe(node, {
      attributes:true, attributeFilter:['class', 'style', 'hidden', 'aria-hidden', 'inert'],
    });
  }
  function mountPanel(first) {
    const usable = candidate => {
      const rect = dockRect(candidate);
      return rect && rect.width >= 170 && rect.height >= 60 && containsHistory(candidate);
    };
    let root = first ? historyDock(first.anchor, first.scope) : null;
    if (!usable(root)) root = null;
    if (!root && usable(dockRoot)) root = dockRoot;
    if (!root) for (const region of document.querySelectorAll(HISTORY_SCOPES)) {
      const candidate = historyDock(region, region);
      if (usable(candidate)) { root = candidate; break; }
    }
    if (!root) for (const item of loaded.values()) {
      const candidate = historyDock(item.anchor, item.scope);
      if (usable(candidate)) { root = candidate; break; }
    }
    if (root !== dockRoot) {
      if (dockRoot) panelObserver?.unobserve(dockRoot);
      dockSpacer.remove();
      dockSpacer.hidden = true;
      spacerLayoutKey = '';
      dockRoot = root;
      if (dockRoot) panelObserver?.observe(dockRoot);
    }
    watchDock(root);
    if (panel.parentElement !== document.body) document.body.append(panel);
    if (root) {
      if (dockSpacer.parentElement !== root) root.append(dockSpacer);
    }
    positionPanel();
  }
  function hidePanel() {
    panel.hidden = true;
    dockSpacer.hidden = true;
    spacerLayoutKey = '';
  }
  function positionPanel() {
    const root = dockRoot;
    const viewportHeight = window.innerHeight;
    const place = rect => {
      if (!rect) return false;
      const {left, right, top, bottom} = rect;
      if (rect.width >= 170 && rect.height >= 60) {
        panel.style.left = `${Math.round(left + 8)}px`;
        panel.style.bottom = `${Math.round(viewportHeight - bottom + 8)}px`;
        panel.style.width = `${Math.floor(right - left - 16)}px`;
        panel.style.maxHeight = `${Math.floor(bottom - top - 16)}px`;
        return true;
      }
      return false;
    };
    if (containsHistory(root)) {
      let rect = dockRect(root);
      if (place(rect)) {
        panel.hidden = false;
        const height = `${Math.ceil(panel.getBoundingClientRect().height + 16)}px`;
        const key = `${rect.width}:${rect.height}:${height}`;
        if (spacerLayoutKey !== key) {
          // Reserve space only when it does not resize the history container.
          // Cache the result so ordinary scrolling never removes the spacer.
          const scrollTop = root.scrollTop, scrollLeft = root.scrollLeft;
          dockSpacer.hidden = true;
          const baseline = root.getBoundingClientRect().height;
          dockSpacer.style.height = height;
          dockSpacer.hidden = false;
          if (Math.abs(root.getBoundingClientRect().height - baseline) > 1) dockSpacer.hidden = true;
          rect = dockRect(root);
          if (!place(rect)) { hidePanel(); return; }
          spacerLayoutKey = `${rect.width}:${rect.height}:${height}`;
          root.scrollTop = scrollTop;
          root.scrollLeft = scrollLeft;
        }
        return;
      }
    }
    hidePanel();
  }
  function scan() {
    scheduleId = 0;
    for (const record of [...records.values()]) {
      if (record.hiddenRow && !ownsConversationRow(record.hiddenRow, record.anchor)) {
        record.hiddenRow.classList.remove('cgbm-done');
        record.hiddenRow = null;
      }
      if (!record.anchor.isConnected || record.anchor.parentElement !== record.parent ||
          !record.wrapper.isConnected || conversationId(record.anchor) !== record.id || !scopeOf(record.anchor)) detach(record);
    }
    const next = new Map();
    let first = null;
    for (const anchor of document.querySelectorAll('a[href*="/c/"]')) {
      const id = conversationId(anchor);
      const scope = scopeOf(anchor);
      if (!id || !scope) continue;
      if (!completed.has(id) && !visible(anchor)) continue;
      const record = records.get(anchor) || attach(anchor, id);
      if (!record) continue;
      if (completed.has(id)) { markDone(record); continue; }
      const title = titleOf(anchor);
      record.input.setAttribute('aria-label', `选择会话：${title}`);
      record.wrapper.title = title;
      if (!next.has(id)) next.set(id, {id, title, anchor, scope});
      if (!first) first = {anchor, scope};
    }
    loaded = next;
    mountPanel(first);
    for (const record of records.values()) position(record);
    render();
  }
  function scheduleScan() {
    if (!scheduleId) scheduleId = window.setTimeout(scan, 120);
  }
  function render() {
    const locked = phase !== 'idle';
    const loadedSelected = [...loaded.keys()].filter(id => selected.has(id)).length;
    counts.textContent = collapsed ? `已选 ${selected.size}` : `已选 ${selected.size} / 已加载 ${loaded.size}`;
    counts.title = selected.size > loadedSelected ? `含 ${selected.size - loadedSelected} 个当前未显示的已选会话，确认时可检查完整清单。` : '';
    selectAll.checked = loaded.size > 0 && loadedSelected === loaded.size;
    selectAll.indeterminate = loadedSelected > 0 && loadedSelected < loaded.size;
    selectAll.disabled = locked || !loaded.size;
    clear.disabled = locked || !selected.size;
    archive.disabled = remove.disabled = locked || !selected.size || refreshRequired;
    refresh.disabled = locked;
    stop.hidden = phase !== 'running';
    stop.disabled = stopRequested;
    // Keep the live status outside an aria-busy subtree so progress is announced.
    actions.setAttribute('aria-busy', String(locked));
    for (const record of records.values()) {
      record.input.checked = selected.has(record.id);
      record.input.disabled = locked || completed.has(record.id);
      const value = String(record.input.checked);
      if (record.anchor.dataset.cgbmSelected !== value) record.anchor.dataset.cgbmSelected = value;
    }
    if (!lastMessage) {
      status.textContent = loaded.size ? '仅处理已勾选的会话；向下滚动侧栏可加载更多。' : '请展开左侧历史记录。未识别到会话时，不会执行任何操作。';
    }
  }
  function setStatus(message, tone = '') {
    lastMessage = message;
    status.textContent = message;
    status.dataset.tone = tone;
  }
  function appendLog(item, result) {
    log.append(el('li', '', `${item.title}〔${item.id}〕：${result}`));
    details.hidden = false;
  }

  class OperationError extends Error {
    constructor(message, uncertain = false) { super(message); this.uncertain = uncertain; }
  }
  async function requestJSON(path, options = {}, mutating = false) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
      const response = await fetch(new URL(path, location.origin), {
        ...options, credentials:'same-origin', cache:'no-store', redirect:'error', signal:controller.signal,
        headers:{Accept:'application/json', ...options.headers},
      });
      if (!response.ok) {
        let message = `请求失败（HTTP ${response.status}）。`;
        if (response.status === 401) message = '登录已过期，请刷新页面并重新登录。';
        if (response.status === 403) message = '请求被拒绝，请检查登录状态或网站验证。';
        if (response.status === 404) message = '未找到会话或接口已变化，请刷新列表后核实。';
        if (response.status === 429) {
          const after = response.headers.get('Retry-After');
          message = '请求过于频繁，已停止。' + (after && /^\d{1,6}$/.test(after) ? `至少等待 ${after} 秒后再检查。` : '请稍后再检查。');
        }
        throw new OperationError(message, mutating && (response.status >= 500 || response.status === 408));
      }
      if (!/\bapplication\/(?:[\w.+-]*\+)?json\b/i.test(response.headers.get('content-type') || '')) {
        throw new OperationError('网站未返回预期的 JSON，可能需要登录/验证或接口已经变化。', mutating);
      }
      try { return await response.json(); }
      catch { throw new OperationError('无法解析服务器响应，请刷新页面核实结果。', mutating); }
    } catch (error) {
      if (error instanceof OperationError) throw error;
      throw new OperationError(controller.signal.aborted ? '请求超时。' : '网络异常或请求被浏览器阻止。', mutating);
    } finally { clearTimeout(timer); }
  }
  async function session() {
    const result = await requestJSON('/api/auth/session');
    if (!result || typeof result.accessToken !== 'string' || !result.accessToken || typeof result.user?.id !== 'string' || !result.user.id) {
      throw new OperationError('无法取得当前登录状态，请登录 ChatGPT 后刷新页面。');
    }
    return {token:result.accessToken, userId:result.user.id};
  }
  function authHeaders(token) {
    return {Authorization:`Bearer ${token}`};
  }

  function confirmBatch(action, items) {
    return new Promise(resolve => {
      const dialog = el('dialog', 'cgbm-ui');
      dialog.id = 'cgbm-confirm';
      dialog.setAttribute('aria-labelledby', 'cgbm-confirm-title');
      dialog.setAttribute('aria-describedby', 'cgbm-confirm-description');
      const isDelete = action === 'delete';
      const verb = isDelete ? '删除' : '归档';
      const title = el('h2', '', `批量${verb} ${items.length} 个会话？`);
      title.id = 'cgbm-confirm-title';
      const description = el('p', '', isDelete ? '删除后无法恢复。请核对下面的完整清单，操作只针对这些会话。' : '会话将从侧栏移除，之后可在设置的“已归档聊天”中恢复。');
      description.id = 'cgbm-confirm-description';
      const list = el('ol', 'cgbm-confirm-list');
      for (const item of items) {
        const row = el('li');
        row.append(el('span', '', item.title), el('code', '', item.id));
        list.append(row);
      }
      const buttons = el('div', 'cgbm-actions');
      const cancel = button('cancel', '取消', () => dialog.close('cancel'));
      cancel.autofocus = true;
      const commit = button('confirm', `确认${verb} ${items.length} 个`, () => dialog.close('commit'), isDelete ? 'cgbm-danger cgbm-commit' : '');
      buttons.append(cancel, commit);
      dialog.append(title, description, list, buttons);
      const finish = () => {
        const accepted = dialog.returnValue === 'commit';
        dialog.remove();
        resolve(accepted);
      };
      dialog.addEventListener('close', finish, {once:true});
      document.body.append(dialog);
      if (typeof dialog.showModal !== 'function') {
        dialog.remove();
        setStatus('此浏览器不支持安全确认窗口，请升级浏览器后再试。', 'error');
        resolve(false);
        return;
      }
      dialog.showModal();
      cancel.focus();
    });
  }

  async function requestBatch(action) {
    if (!['archive','delete'].includes(action) || phase !== 'idle' || !selected.size || refreshRequired) return;
    const trigger = action === 'delete' ? remove : archive;
    const items = [...selected.values()].map(item => Object.freeze({...item}));
    const verb = action === 'delete' ? '删除' : '归档';
    phase = 'checking'; stopRequested = false;
    setStatus('正在核对登录状态…'); render();
    let success = 0, failed = 0, uncertain = 0;
    try {
      const {userId} = await session();
      phase = 'confirming'; render();
      const accepted = await confirmBatch(action, items);
      if (!accepted) { setStatus('已取消，未发送任何会话修改请求。'); return; }
      phase = 'running';
      log.replaceChildren(); details.hidden = true;
      progress.max = items.length; progress.value = 0; progress.hidden = false;
      render();
      for (const item of items) {
        if (stopRequested) break;
        try {
          setStatus(`正在${verb} ${success + 1}/${items.length}：${item.title}`);
          // Recheck identity per item; do not reuse a token across account switches.
          const auth = await session();
          if (stopRequested) break;
          if (auth.userId !== userId) throw new OperationError('登录账号已改变，后续操作已停止。请刷新后重新选择会话。');
          const result = await requestJSON(`/backend-api/conversation/${item.id}`, {
            method:'PATCH', headers:{...authHeaders(auth.token), 'Content-Type':'application/json'},
            body:JSON.stringify(action === 'archive' ? {is_archived:true} : {is_visible:false}),
          }, true);
          if (result?.success !== true) {
            throw new OperationError(result?.success === false ? '服务器未确认成功，已停止。' : '服务器响应格式发生变化，结果待核实。', result?.success !== false);
          }
          success++;
          completed.add(item.id); selected.delete(item.id);
          appendLog(item, `已${verb}`);
          for (const record of records.values()) if (record.id === item.id) markDone(record);
          loaded.delete(item.id);
          progress.value = success;
          render();
        } catch (error) {
          if (error.uncertain) {
            uncertain++; refreshRequired = true;
            appendLog(item, `结果待核实：${error.message} 请刷新列表检查；不会自动重试。`);
          } else {
            failed++;
            appendLog(item, `未完成：${error.message}`);
          }
          details.open = true;
          stopRequested = true;
          break;
        }
        if (!stopRequested && success < items.length) await new Promise(resolve => setTimeout(resolve, GAP_MS));
      }
      const remaining = items.length - success - uncertain - failed;
      const outcome = `已${verb} ${success}；未完成 ${failed}；待核实 ${uncertain}；未处理 ${Math.max(0,remaining)}。`;
      const advice = uncertain ? '请先刷新列表核实结果。' : (success ? '可点击“刷新列表”同步页面。' : '未成功的会话保留选择，可查看操作结果。');
      setStatus(outcome + advice, failed || uncertain ? 'error' : '');
    } catch (error) {
      setStatus(`操作已停止：${error.message || '发生未知错误，请刷新后重试。'}`, 'error');
    } finally {
      phase = 'idle';
      // Refresh is user-controlled to preserve unsent drafts.
      render(); scheduleScan();
      const focusTarget = !trigger.disabled ? trigger : refresh;
      focusTarget.focus({preventScroll:true});
    }
  }

  // Observe sidebar changes, not streamed text. Ignore our own text/style mutations.
  const observer = new MutationObserver(mutations => {
    if (mutations.some(m => {
      const node = m.target instanceof Element ? m.target : m.target.parentElement;
      if (!node || node.closest('.cgbm-ui')) return false;
      if (m.type === 'attributes') return m.attributeName === 'href' || node === document.documentElement;
      if (node.closest(EXCLUDE)) return false;
      return [...m.addedNodes, ...m.removedNodes].some(n => !(n instanceof Element && n.classList.contains('cgbm-ui')));
    })) scheduleScan();
  });
  observer.observe(document.body, {childList:true, subtree:true, attributes:true, attributeFilter:['href']});
  observer.observe(document.documentElement, {attributes:true, attributeFilter:['class', 'data-theme']});
  let positionFrame = 0;
  const reposition = () => {
    if (!positionFrame) positionFrame = requestAnimationFrame(() => {
      positionFrame = 0;
      positionPanel();
      for (const record of records.values()) position(record);
    });
  };
  const panelObserver = typeof ResizeObserver === 'function' ? new ResizeObserver(reposition) : null;
  const dockAttributeObserver = new MutationObserver(() => { reposition(); scheduleScan(); });
  panelObserver?.observe(panel);
  window.addEventListener('scroll', reposition, {capture:true, passive:true});
  window.addEventListener('resize', scheduleScan, {passive:true});
  window.addEventListener('popstate', scheduleScan);
  window.addEventListener('pageshow', scheduleScan);
  window.addEventListener('beforeunload', event => {
    if (phase === 'running') { event.preventDefault(); event.returnValue = ''; }
  });
  // Covers SPA re-mounts and sidebar collapse without patching site code.
  window.setInterval(scheduleScan, 1600);
  scan();
})();
