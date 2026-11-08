(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('boss-data').textContent);
  const $ = id => document.getElementById(id);
  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const svgEl = (tag, attrs, text) => {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const number = value => value === null ? '待确认' : new Intl.NumberFormat('zh-CN', {maximumFractionDigits: 2}).format(value);
  const palette = ['#17654e', '#69826a', '#9b6428', '#557982', '#815977'];
  const negative = '#a63e32';
  const targets = new Map();
  const register = (section, index, node) => targets.set(section + ':' + index, node);
  function addDefinition(target, label, value) { target.append(el('dt', label), el('dd', value)); }
  function legend(labels, panel) {
    if (!labels.length) return;
    const node = el('div', null, 'legend');
    labels.forEach((label, index) => { const item = el('span'); const mark = el('i'); mark.style.background = palette[index % palette.length]; item.append(mark, document.createTextNode(label)); node.append(item); });
    panel.append(node);
  }
  function bars(chart, panel) {
    const groups = [...new Set(chart.series.map(point => point.group).filter(Boolean))];
    legend(groups, panel);
    const known = chart.series.filter(point => point.value !== null).map(point => point.value);
    const min = Math.min(0, ...known); const max = Math.max(0, ...known); const span = max - min || 1;
    const position = value => (value - min) / span * 100;
    const plot = el('div', null, 'bar-plot');
    chart.series.forEach(point => {
      const row = el('div', null, 'bar-row'); row.append(el('span', point.label, 'bar-label'));
      const track = el('div', null, 'bar-track'); const zero = el('i', null, 'bar-zero'); zero.style.left = position(0) + '%'; track.append(zero);
      if (point.value !== null) {
        const bar = el('i', null, 'bar-fill'); bar.style.left = Math.min(position(0), position(point.value)) + '%'; bar.style.width = Math.abs(position(point.value) - position(0)) + '%';
        bar.style.background = point.value < 0 ? negative : palette[Math.max(0, groups.indexOf(point.group)) % palette.length]; track.append(bar);
      }
      track.setAttribute('aria-hidden', 'true');
      row.append(track, el('span', number(point.value), 'bar-value' + (point.value === null ? ' unknown' : point.value < 0 ? ' negative' : ''))); plot.append(row);
    });
    panel.append(plot);
  }
  function stacked(chart, panel) {
    const labels = [...new Set(chart.series.map(point => point.label))];
    const groups = [...new Set(chart.series.map(point => point.group || '当前构成'))];
    legend(labels, panel);
    const rows = groups.map(group => {
      const points = chart.series.filter(point => (point.group || '当前构成') === group);
      return {group, points, valid: points.every(point => point.value !== null && point.value >= 0), total: points.reduce((sum, point) => sum + (point.value ?? 0), 0)};
    });
    const max = Math.max(1, ...rows.filter(row => row.valid).map(row => row.total));
    const plot = el('div', null, 'stacked');
    rows.forEach(row => {
      const node = el('div', null, 'stack-row'); const label = el('div', row.group, 'stack-label'); label.append(el('span', row.valid ? number(row.total) + ' ' + chart.unit : '待确认')); node.append(label);
      const track = el('div', null, 'stack-track');
      if (!row.valid) track.append(el('span', '构成未齐，先看下方数值', 'stack-message'));
      else if (row.total === 0) track.append(el('span', '0', 'stack-message'));
      else row.points.forEach(point => { const piece = el('span', point.value / max > .16 ? number(point.value) : '', 'stack-piece'); piece.style.width = point.value / max * 100 + '%'; piece.style.background = palette[labels.indexOf(point.label) % palette.length]; piece.title = point.label + '：' + number(point.value) + ' ' + chart.unit; piece.setAttribute('aria-label', piece.title); track.append(piece); });
      node.append(track); plot.append(node);
    });
    panel.append(plot);
  }
  function waterfall(chart, panel) {
    if (chart.series.some(point => point.value === null)) { panel.append(el('p', '关键金额待确认，补齐后再看完整收支变化。', 'empty-chart')); return; }
    let running = 0;
    const points = chart.series.map(point => {
      const change = point.role === 'decrease' ? -Math.abs(point.value) : point.value;
      const start = point.role === 'total' ? 0 : running;
      running = point.role === 'total' ? point.value : running + change;
      return {...point, change, start, end: running};
    });
    const min = Math.min(0, ...points.flatMap(point => [point.start, point.end]));
    const max = Math.max(0, ...points.flatMap(point => [point.start, point.end]));
    const y = value => 183 - (value - min) / (max - min || 1) * 128;
    const step = 420 / Math.max(points.length, 1); const width = Math.min(58, step * .6);
    const svg = svgEl('svg', {viewBox: '0 0 460 241', class: 'waterfall', role: 'img', 'aria-label': chart.title + '，完整数值见下方表格'});
    for (let index = 0; index < 4; index++) { const value = min + (max - min) * index / 3; svg.append(svgEl('line', {x1: 20, x2: 445, y1: y(value), y2: y(value), stroke: '#dce5dc', 'stroke-dasharray': '3 4'})); }
    points.forEach((point, index) => {
      const x = 20 + step * index + (step - width) / 2;
      const top = Math.min(y(point.start), y(point.end));
      const fill = point.role === 'total' ? palette[0] : point.change < 0 ? negative : palette[1];
      svg.append(svgEl('rect', {x, y: top, width, height: Math.max(1, Math.abs(y(point.end) - y(point.start))), rx: 2, fill}));
      svg.append(svgEl('text', {x: x + width / 2, y: top - 9, 'text-anchor': 'middle', class: 'number'}, (point.role !== 'total' && point.change > 0 ? '+' : '') + number(point.role === 'total' ? point.value : point.change)));
      const label = svgEl('text', {x: x + width / 2, y: 208, 'text-anchor': 'middle'});
      const chunks = point.label.match(/.{1,6}/gu) || [''];
      chunks.forEach((chunk, line) => label.append(svgEl('tspan', {x: x + width / 2, dy: line === 0 ? 0 : 16}, chunk))); svg.append(label);
      if (index < points.length - 1) svg.append(svgEl('line', {x1: x + width, x2: x + step, y1: y(point.end), y2: y(point.end), stroke: '#a9bbaa', 'stroke-dasharray': '3 3'}));
    });
    panel.append(svg);
  }
  function chartTable(chart) {
    const details = el('details'); details.append(el('summary', '查看完整数值'));
    const scroll = el('div', null, 'table-scroll'); scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', chart.title + '数据表，可横向滚动');
    const table = el('table'); const head = el('thead'); const header = el('tr');
    ['项目', '分组', '数值（' + chart.unit + '）'].forEach(text => { const th = el('th', text); th.scope = 'col'; header.append(th); }); head.append(header); table.append(head);
    const body = el('tbody'); chart.series.forEach(point => { const row = el('tr'); [point.label, point.group || '—', number(point.value)].forEach(text => row.append(el('td', text))); body.append(row); }); table.append(body); scroll.append(table); details.append(scroll); return details;
  }
  const first = data.actions[0];
  document.title = data.merchant.name + ' · 经营行动方案';
  $('merchant').textContent = data.merchant.name;
  $('synthetic').hidden = !data.merchant.synthetic;
  $('headline').textContent = data.headline;
  $('scope').textContent = [data.merchant.scope, data.merchant.period].filter(Boolean).join(' · ');
  $('money-label').textContent = data.money.label;
  $('money-value').textContent = (data.money.value > 0 && /增加|增量|改善|多赚|提升|节省/.test(data.money.label) ? '+' : '') + number(data.money.value);
  $('money-value').className = data.money.value === null ? 'unknown' : '';
  $('money-unit').textContent = data.money.value === null ? '' : data.money.unit;
  $('money-period').textContent = data.money.period;
  $('money-note').textContent = data.money.note; $('money-note').hidden = !data.money.note;
  $('money-basis').hidden = !data.money.basis; $('money-basis').querySelector('p').textContent = data.money.basis;
  register('money', 0, document.querySelector('.money-panel'));
  $('first-action-title').textContent = first.title;
  [['负责', first.owner], ['时间', first.timing], ['投入', first.budget]].forEach(([label, value]) => addDefinition($('first-action-meta'), label, value));
  $('charts').className = 'charts' + (data.charts.length === 1 ? ' one' : data.charts.length === 2 ? ' two' : '');
  $('charts').hidden = !data.charts.length;
  data.charts.forEach((chart, index) => { const panel = el('article', null, 'chart'); panel.append(el('h3', chart.title), el('p', '单位：' + chart.unit, 'chart-unit')); ({bar: bars, stacked, waterfall}[chart.type])(chart, panel); if (chart.caption) panel.append(el('p', chart.caption, 'chart-caption')); panel.append(chartTable(chart)); $('charts').append(panel); register('charts', index, panel); });
  $('findings').hidden = !data.findings.length;
  data.findings.forEach((finding, index) => { const article = el('article', null, 'finding'); article.append(el('h3', finding.title)); const body = el('div'); body.append(el('p', finding.detail)); if (finding.basis) body.append(el('p', finding.basis, 'basis')); article.append(body); $('findings').append(article); register('findings', index, article); });
  $('dashboard').hidden = !data.charts.length && !data.findings.length;
  if ($('dashboard').hidden) document.querySelector('nav a[href="#dashboard"]').hidden = true;
  data.actions.forEach((action, index) => {
    const article = el('article', null, 'action'); const heading = el('div', null, 'action-title'); heading.append(el('h3', action.title), el('p', action.owner + ' · ' + action.timing)); article.append(heading);
    const list = el('dl'); [['投入', action.budget], ['继续条件', action.success], ['什么时候停', action.stop]].forEach(([label, value]) => { const pair = el('div', null, label === '什么时候停' ? 'stop' : ''); addDefinition(pair, label, value); list.append(pair); }); article.append(list); $('actions').append(article); register('actions', index, article);
  });
  const audienceRows = [];
  const audiencePlan = data.audience_plan || [];
  $('audience').hidden = !audiencePlan.length;
  audiencePlan.forEach((row, index) => {
    const wrapper = el('article', null, 'audience-option');
    const button = el('button', null, 'audience-select'); button.type = 'button';
    button.setAttribute('aria-pressed', String(index === 0));
    button.setAttribute('aria-expanded', String(index === 0));
    const detailId = 'audience-detail-' + index; button.setAttribute('aria-controls', detailId);
    [row.audience, row.product, row.benefit, row.decision].forEach((text, column) => {
      const item = el('span', text); item.dataset.label = ['人群', '匹配商品', '权益', '本次决策'][column]; button.append(item);
    });
    const detail = el('div', null, 'audience-detail'); detail.id = detailId; detail.hidden = index !== 0;
    const list = el('dl');
    if (row.basis) addDefinition(list, '材料依据', row.basis);
    addDefinition(list, '如何验收', row.validation);
    if (row.economics) {
      const amount = number(row.economics.value) + (row.economics.value === null ? '' : ' ' + row.economics.unit);
      addDefinition(list, row.economics.label, amount);
    }
    detail.append(list); wrapper.append(button, detail); $('audience-options').append(wrapper);
    register('audience_plan', index, wrapper); audienceRows.push({button, detail});
    button.addEventListener('click', () => {
      audienceRows.forEach(entry => {
        const selected = entry.button === button;
        entry.button.setAttribute('aria-pressed', String(selected));
        entry.button.setAttribute('aria-expanded', String(selected));
        entry.detail.hidden = !selected;
      });
    });
  });
  $('gaps').hidden = !data.gaps.length;
  if (data.gaps.length) { $('gaps').append(el('h3', '还需要确认什么')); data.gaps.forEach(gap => { const row = el('div', null, 'gap'); row.append(el('strong', gap.item), el('p', gap.why)); $('gaps').append(row); }); }
  const follow = $('followup').querySelector('dl');
  addDefinition(follow, '复盘时间', data.followup.when);
  addDefinition(follow, '需要回传', data.followup.collect.length ? data.followup.collect.join('；') : '按行动安排记录实际执行情况');
  addDefinition(follow, '再做决定', data.followup.decision);
  $('footer-merchant').textContent = data.merchant.name + ' · 经营行动方案';
  const methods = data.methods || [];
  const annotations = [];
  let currentAnnotation = null;
  function explanationContent(method) {
    const list = el('dl', null, 'method-explanation');
    if (method.basis) addDefinition(list, '材料依据', method.basis);
    addDefinition(list, '方法来源', method.origin);
    addDefinition(list, '本次判断', method.decision);
    addDefinition(list, '适配理由', method.reason);
    const actionIndexes = [...new Set(method.anchors.filter(anchor => anchor.section === 'actions').map(anchor => anchor.index))];
    if (actionIndexes.length) addDefinition(list, '对应执行', actionIndexes.map(index => {
      const action = data.actions[index]; return action.title + '（' + action.owner + ' · ' + action.timing + '）';
    }).join('；'));
    return list;
  }
  function closeAnnotation(returnFocus = false) {
    if (!currentAnnotation) return;
    const active = currentAnnotation;
    active.panel.hidden = true; active.button.setAttribute('aria-expanded', 'false');
    currentAnnotation = null;
    if (returnFocus) active.button.focus();
  }
  function openAnnotation(annotation) {
    if (currentAnnotation === annotation) { closeAnnotation(); return; }
    closeAnnotation(); annotation.panel.hidden = false; annotation.button.setAttribute('aria-expanded', 'true');
    currentAnnotation = annotation;
  }
  function annotationIcon() {
    const icon = svgEl('svg', {viewBox: '0 0 20 20', width: 20, height: 20, 'aria-hidden': 'true', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.5});
    icon.append(svgEl('circle', {cx: 10, cy: 10, r: 7}), svgEl('path', {d: 'M10 7v6M7 10h6'}));
    return icon;
  }
  methods.forEach((method, index) => {
    const record = el('details', null, 'method-record');
    const summary = el('summary'); summary.append(el('strong', method.name), el('span', method.status, 'method-status' + (method.used ? ' used' : '')));
    record.append(summary, explanationContent(method)); $('method-records').append(record);
    if (!method.used || !method.basis || annotations.length >= 3) return;
    const anchor = method.anchors.find(target => targets.has(target.section + ':' + target.index));
    if (!anchor) return;
    const target = targets.get(anchor.section + ':' + anchor.index);
    const container = el('div', null, 'method-callout explain-only'); container.hidden = true;
    const button = el('button', null, 'method-marker'); button.type = 'button';
    button.append(annotationIcon(), el('span', '看方法 · ' + method.name));
    button.setAttribute('aria-expanded', 'false'); button.setAttribute('aria-controls', 'method-detail-' + index);
    const panel = el('section', null, 'method-detail'); panel.id = 'method-detail-' + index; panel.hidden = true;
    panel.setAttribute('aria-label', method.name + '的判断依据');
    const header = el('div', null, 'method-detail-heading'); header.append(el('h4', method.name));
    const close = el('button', '收起', 'method-close'); close.type = 'button'; close.setAttribute('aria-label', '收起' + method.name + '讲解'); header.append(close);
    panel.append(header, explanationContent(method)); container.append(button, panel); target.append(container);
    const annotation = {button, panel, container}; annotations.push(annotation);
    const jump = el('button', method.name, 'explanation-jump'); jump.type = 'button';
    jump.addEventListener('click', () => { if (currentAnnotation !== annotation) openAnnotation(annotation); button.scrollIntoView({block: 'center'}); button.focus({preventScroll: true}); });
    $('explanation-links').append(jump);
    button.addEventListener('click', () => openAnnotation(annotation));
    close.addEventListener('click', () => closeAnnotation(true));
  });
  $('view-mode').hidden = !methods.length;
  function setMode(explaining) {
    closeAnnotation(); document.body.classList.toggle('explaining', explaining);
    $('mode-boss').setAttribute('aria-pressed', String(!explaining));
    $('mode-product').setAttribute('aria-pressed', String(explaining));
    $('methods').hidden = !explaining;
    $('explanation-guide').hidden = !explaining || !annotations.length;
    annotations.forEach(annotation => { annotation.container.hidden = !explaining; });
    if (explaining) toast(annotations.length ? '产品讲解已开启，点击方案中的“看方法”查看判断依据。' : '产品讲解已开启，可在页尾查看每项方法的适用情况。');
  }
  $('mode-boss').addEventListener('click', () => setMode(false));
  $('mode-product').addEventListener('click', () => setMode(true));
  let toastTimer;
  function toast(message) { $('toast').textContent = message; clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('toast').textContent = ''; }, 3500); }
  $('copy').addEventListener('click', async () => {
    const money = data.money.label + '：' + number(data.money.value) + (data.money.value === null ? '' : data.money.unit) + '（' + data.money.period + '）';
    const text = [data.merchant.name + '｜经营行动方案', data.merchant.synthetic ? $('synthetic').textContent : '', data.headline, money, data.money.note, '先做：' + first.title, '负责：' + first.owner + '；时间：' + first.timing + '；投入：' + first.budget, '停止条件：' + first.stop, '复盘：' + data.followup.when + '，' + data.followup.decision].filter(Boolean).join('\n');
    $('copy').disabled = true;
    try { if (!navigator.clipboard) throw new Error('Clipboard unavailable'); await navigator.clipboard.writeText(text); toast('摘要已复制'); }
    catch { $('copy-fallback').hidden = false; $('copy-text').value = text; $('copy-text').focus(); $('copy-text').select(); }
    finally { $('copy').disabled = false; }
  });
  $('close-copy').addEventListener('click', () => { $('copy-fallback').hidden = true; $('copy').focus(); });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    if (!$('copy-fallback').hidden) { $('copy-fallback').hidden = true; $('copy').focus(); }
    else closeAnnotation(true);
  });
  $('print').addEventListener('click', () => window.print());
  let printState = [];
  window.addEventListener('beforeprint', () => { printState = [...document.querySelectorAll('details')].map(node => ({node, open: node.open})); printState.forEach(({node}) => { node.open = true; }); });
  window.addEventListener('afterprint', () => { printState.forEach(({node, open}) => { node.open = open; }); printState = []; });
  if (methods.length && new URLSearchParams(window.location.search).get('view') === 'explain') setMode(true);
})();
