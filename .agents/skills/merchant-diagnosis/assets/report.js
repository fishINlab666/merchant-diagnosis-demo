(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('report-data').textContent);
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
  const number = value => value === null ? '待补数' : new Intl.NumberFormat('zh-CN', {maximumFractionDigits: 2}).format(value);
  const colors = ['#17644f', '#8baf95', '#bd702f', '#5f7c89', '#b04138'];
  const stageNames = {S1:'公开初诊', S2:'定向补数', S3:'数据核对', S4:'经营诊断', S5:'行动方案'};
  let currentCase = data.cases[0];
  let currentVersion;
  let toastTimer;
  let printDetails = [];
  function toast(message) { $('toast').textContent = message; clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('toast').textContent = ''; }, 3500); }
  function option(value, label) { const node = el('option', label); node.value = value; return node; }
  function disclosure(label, content) { const node = el('details'); node.append(el('summary', label), content); return node; }
  function table(headers, rows) {
    const wrap = el('div', null, 'table-scroll'); wrap.tabIndex = 0; wrap.setAttribute('role', 'region'); wrap.setAttribute('aria-label', '数据表，可横向滚动');
    const node = el('table'); const head = el('thead'); const tr = el('tr');
    headers.forEach(header => { const th = el('th', header); th.scope = 'col'; tr.append(th); }); head.append(tr); node.append(head);
    const body = el('tbody'); rows.forEach(row => { const item = el('tr'); row.forEach(cell => item.append(el('td', cell))); body.append(item); }); node.append(body); wrap.append(node); return wrap;
  }
  function sectionBlocks(stage, heading) {
    if (!stage) return [];
    const blocks = []; let inside = false;
    for (const block of stage.blocks) {
      if (block.type === 'heading') { if (inside) break; inside = block.text === heading; }
      else if (inside) blocks.push(block);
    }
    return blocks;
  }
  function sectionTable(stage, heading) { return sectionBlocks(stage, heading).find(block => block.type === 'table'); }
  function records(tableBlock) { return (tableBlock?.rows || []).map(row => Object.fromEntries(tableBlock.headers.map((key, index) => [key, row[index] || '']))); }
  function definitions(entries) { const node = el('dl'); entries.filter(([, value]) => value).forEach(([key, value]) => {node.append(el('dt', key), el('dd', value));}); return node; }
  function stage(id) { return currentVersion.stages.find(item => item.stage === id); }
  function renderMetrics() {
    const items = currentVersion.visuals.highlights;
    $('metrics').replaceChildren(); $('metrics').hidden = !items.length;
    items.forEach(item => {
      const node = el('div', null, 'metric'); node.append(el('p', item.label, 'metric-label'));
      const value = el('p', number(item.value), 'metric-value' + (item.value === null ? ' unknown' : item.value < 0 ? ' negative' : ''));
      if (item.value !== null) value.append(el('small', item.unit));
      node.append(value, el('p', item.note, 'metric-note'), disclosure('数据依据', el('p', item.evidence))); $('metrics').append(node);
    });
  }
  function legend(groups, palette = colors) {
    const node = el('div', null, 'chart-legend'); groups.forEach((group, index) => { const item = el('span'); const swatch = el('i', null, 'swatch'); swatch.style.background = palette[index % palette.length]; item.append(swatch, document.createTextNode(group)); node.append(item); }); return node;
  }
  function bars(chart, panel) {
    const groups = [...new Set(chart.series.map(item => item.group).filter(Boolean))];
    if (groups.length) panel.append(legend(groups, groups.map((group,index) => {
      const values = chart.series.filter(point => point.group === group && point.value !== null);
      return values.length && values.every(point => point.value < 0) ? '#b04138' : colors[index % colors.length];
    })));
    const values = chart.series.filter(item => item.value !== null).map(item => item.value);
    let min = Math.min(0, ...values); let max = Math.max(0, ...values);
    if (min === max) max = min + 1;
    const x = value => (value - min) / (max - min) * 100;
    const plot = el('div',null,'bar-plot'); const axis = el('div',null,'bar-axis');
    [min,(min+max)/2,max].forEach(value=>axis.append(el('span',number(value)))); plot.append(axis);
    chart.series.forEach(point => {
      const row = el('div',null,'bar-row'); row.append(el('span',point.label,'bar-label'));
      const track = el('div',null,'bar-track'); const zero = el('i',null,'bar-zero');zero.style.left=x(0)+'%';track.append(zero);
      const fill = point.value < 0 ? '#b04138' : colors[Math.max(0, groups.indexOf(point.group)) % colors.length];
      if (point.value !== null) {const bar=el('i',null,'bar-fill');bar.style.left=Math.min(x(0),x(point.value))+'%';bar.style.width=Math.abs(x(point.value)-x(0))+'%';bar.style.background=fill;track.append(bar);}
      row.append(track,el('span',number(point.value),'bar-number'));plot.append(row);
    }); panel.append(plot);
  }
  function stacked(chart, panel) {
    const labels = [...new Set(chart.series.map(item => item.label))];
    const groups = [...new Set(chart.series.map(item => item.group || '构成'))];
    panel.append(legend(labels)); const wrap = el('div', null, 'stacked');
    const groupTotals = groups.map(group => chart.series.filter(item => (item.group || '构成') === group).reduce((sum, item) => sum + (item.value ?? 0), 0));
    const maximum = Math.max(1, ...groupTotals);
    groups.forEach((group, index) => {
      const points = chart.series.filter(item => (item.group || '构成') === group); const row = el('div', null, 'stack-row'); const title = el('div', group, 'stack-label');
      const hasUnknown = points.some(item => item.value === null); const invalid = points.some(item => item.value !== null && item.value < 0);
      title.append(el('span', hasUnknown ? '构成待补齐' : invalid ? '负数不作构成展示' : number(groupTotals[index]) + ' ' + chart.unit)); row.append(title);
      const track = el('div', null, 'stack-track');
      if (hasUnknown || invalid || groupTotals[index] === 0) track.append(el('span', hasUnknown ? '待补数' : invalid ? '请查看数据表' : '0', 'stack-empty'));
      else points.forEach(point => { const piece = el('div', null, 'stack-piece'); piece.style.width = (point.value / maximum * 100) + '%'; piece.style.background = colors[labels.indexOf(point.label) % colors.length]; piece.title = point.label + '：' + number(point.value) + ' ' + chart.unit; if (point.value / maximum >= .12) piece.textContent = number(point.value); piece.setAttribute('aria-label', piece.title); track.append(piece); });
      row.append(track); wrap.append(row);
    }); panel.append(wrap);
  }
  function waterfall(chart, panel) {
    if (chart.series.some(point => point.value === null)) {panel.append(el('p', '数据未齐，暂不绘制贡献变化；详见下方数据表。', 'empty')); return;}
    let running = 0;
    const points = chart.series.map(point => { const total = point.role === 'total'; const start = total ? 0 : running; running = total ? point.value : running + point.value; return {...point,start,end:running}; });
    const min = Math.min(0,...points.flatMap(point => [point.start,point.end])); const max = Math.max(1,...points.flatMap(point => [point.start,point.end]));
    const y = value => 205 - (value-min)/(max-min)*145;
    const svg = svgEl('svg',{viewBox:'0 0 590 259',class:'chart-svg',role:'img','aria-label':chart.title+'，详细数值见下方数据表'});
    for(let i=0;i<=3;i++){const v=min+(max-min)*i/3; svg.append(svgEl('line',{x1:76,x2:582,y1:y(v),y2:y(v),class:'grid'}));svg.append(svgEl('text',{x:68,y:y(v)+4,'text-anchor':'end'},number(v)));}
    const step = 504 / Math.max(points.length,1); const width = Math.min(63,step*.65);
    points.forEach((point,index) => { const x = 76 + step * index + (step-width)/2; const fill = point.role === 'total' ? '#17644f' : point.value < 0 ? '#b04138' : '#8baf95'; const top = Math.min(y(point.start),y(point.end));
      svg.append(svgEl('rect',{x,y:top,width,height:Math.max(1,Math.abs(y(point.end)-y(point.start))),rx:3,fill}));
      svg.append(svgEl('text',{x:x+width/2,y:top-10,'text-anchor':'middle',class:'chart-number'},(point.role!=='total'&&point.value>0?'+':'')+number(point.value)));
      svg.append(svgEl('text',{x:x+width/2,y:230,'text-anchor':'middle'},point.label));
      if(index<points.length-1)svg.append(svgEl('line',{x1:x+width,x2:x+step,y1:y(point.end),y2:y(point.end),stroke:'#9ab0a2','stroke-dasharray':'4 3'}));
    });panel.append(svg);
  }
  function renderCharts() {
    $('charts').replaceChildren();
    currentVersion.visuals.charts.forEach(chart => {
      const panel = el('article', null, 'chart-panel'); const heading = el('div', null, 'chart-heading'); heading.append(el('h3', chart.title),el('span', '单位：'+chart.unit,'unit')); panel.append(heading);
      ({bars,stacked,waterfall}[chart.type])(chart,panel);
      panel.append(el('p',chart.caption,'chart-caption'));
      const details = disclosure('查看数值与口径',table(['项目','分组','数值（'+chart.unit+'）'],chart.series.map(point => [point.label,point.group||'—',number(point.value)])));
      details.className = 'chart-details'; details.append(el('p',chart.evidence)); panel.append(details); $('charts').append(panel);
    });
  }
  function renderFindings() {
    const target = $('findings-content'); target.replaceChildren();
    let items = records(sectionTable(stage('S4'),'优先问题'));
    if(!items.length)items=records(sectionTable(stage('S5'),'问题与证据')).map(item=>({'编号':item['问题编号'],'问题事实':item['问题'],'证据':item['证据']}));
    if(!items.length){target.append(el('p','本轮尚未形成内部经营判断，请查看下方已生成的阶段报告。','empty'));return;}
    items.forEach(item=>{
      const row=el('article',null,'finding');const id=el('div',item['编号'],'finding-id');id.append(el('small',item['优先级']?item['优先级']+'优先':''));
      const content=el('div');content.append(el('h3',item['问题事实']));if(item['处理方向'])content.append(el('p',item['处理方向'],'direction'));
      const more=definitions([['原因判断',item['原因判断']],['判断状态',item['判断状态']],['证据',item['证据']]]);content.append(disclosure('展开判断依据',more));row.append(id,content);target.append(row);
    });
  }
  function renderActions() {
    const target=$('actions-content');target.replaceChildren();const report=stage('S5');
    const actions=records(sectionTable(report,'现在／建议'));const expected=records(sectionTable(report,'预期改善'));const follow=records(sectionTable(report,'下周跟进'));
    if(!actions.length)target.append(el('p','本轮尚未形成行动方案。先按已生成的报告完成定向补数。','empty'));
    actions.forEach(item=>{
      const id=item['动作编号'];const prediction=expected.find(row=>row['动作编号']===id)||{};const next=follow.find(row=>row['动作编号']===id)||{};
      const article=el('article',null,'action');const head=el('div',null,'action-head');head.append(el('span',id,'action-code'),el('p',item['建议']));article.append(head);
      article.append(el('p','时间：'+item['开始时间'],'action-schedule'));
      article.append(disclosure('负责人、投入与现状',definitions([['关联问题',item['关联问题']],['现状',item['现在']],['负责人',item['负责人']],['投入',item['投入']]])));
      article.append(disclosure('指标、目标与复盘条件',definitions([...Object.entries(prediction).filter(([key])=>key!=='动作编号'),...Object.entries(next).filter(([key])=>key!=='动作编号')])));target.append(article);
    });
    const gapTarget=$('gaps');gapTarget.replaceChildren();const s4=stage('S4');
    const gaps=records(sectionTable(s4,'仍需确认') || (!s4 && sectionTable(stage('S2'),'补数清单')));
    if(gaps.length){const panel=el('div',null,'gap-panel');panel.append(el('h3','还需补什么，会改变什么决策'));
      gaps.forEach(item=>{const row=el('div',null,'gap-row');row.append(el('strong',item['缺口编号']));const body=el('div');body.append(el('h4',item['待验证问题']||item['需要材料']));body.append(el('p','决策用途：'+item['决策用途']));body.append(disclosure('需要的材料',el('p',(item['需要材料或试验']||item['需要材料']||'')+(item['时间与范围']?'；'+item['时间与范围']:''))));row.append(body);panel.append(row);});gapTarget.append(panel);}
  }
  function renderBlocks(blocks, target) {
    blocks.forEach(block=>{
      if(block.type==='heading')target.append(el('h3',block.text));
      else if(block.type==='paragraph')target.append(el('p',block.text));
      else if(block.type==='table')target.append(table(block.headers,block.rows));
      else if(block.type==='list'){const list=el('ol');block.items.forEach(item=>list.append(el('li',item)));target.append(list);}
    });
  }
  function renderReports() {
    $('stage-path').replaceChildren();$('reports-content').replaceChildren();
    Object.entries(stageNames).forEach(([id,name])=>{const report=stage(id);const node=el(report?'a':'div',null,'stage-step'+(!report?' absent':''));node.append(el('span',id),document.createTextNode(name),el('small',report?report.metadata.status:'本版本未生成'));
      if(report){node.href='#stage-'+id;node.addEventListener('click',()=>{$('stage-'+id).open=true;});}$('stage-path').append(node);});
    currentVersion.stages.forEach(report=>{const details=el('details',null,'stage-report');details.id='stage-'+report.stage;const summary=el('summary',report.stage+' · '+report.title);summary.append(el('span',report.metadata.status));const body=el('div',null,'stage-body');body.append(el('p',report.metadata.merchant+'\n'+report.metadata.scope,'stage-meta'));renderBlocks(report.blocks,body);details.append(summary,body);$('reports-content').append(details);});
    const index=el('ul');currentVersion.sources.forEach(source=>{const li=el('li',source.name+' ');li.append(el('code',source.sha256));index.append(li);});
    currentVersion.stages.forEach(report=>{const li=el('li',report.stage+'/report.md ');li.append(el('code',report.sha256));index.append(li);});$('sources-content').replaceChildren(el('p','分析执行：'+currentVersion.executor+' · 模型 ID：'+currentVersion.model_id),index);
  }
  function renderVersion(id) {
    currentVersion=currentCase.versions.find(item=>item.id===id);$('version-select').value=id;
    $('case-title').textContent=currentCase.title;$('merchant').textContent=currentVersion.merchant;$('summary').textContent=currentVersion.summary||'请查看已生成的阶段报告。';
    $('scope').textContent=currentVersion.scope;$('data-badge').textContent=currentCase.synthetic?'合成数据演示':'材料属性未作合成标注';
    $('report-status').textContent=currentVersion.status;$('report-status').className='badge'+(currentVersion.status==='可交付'?'':' warn');
    $('version-warning').hidden=!currentVersion.superseded;$('footer-status').textContent='当前展示：'+currentVersion.label+' · 本页为既有分析的展示导出';
    document.title=currentCase.title+' · '+currentVersion.label;
    $('copy-fallback').hidden=true;renderMetrics();renderCharts();renderFindings();renderActions();renderReports();
  }
  function selectCase(id) {currentCase=data.cases.find(item=>item.id===id);$('version-select').replaceChildren(...currentCase.versions.map(item=>option(item.id,item.label)));renderVersion(currentCase.active_version);}
  $('case-select').append(...data.cases.map(item=>option(item.id,item.label)));$('case-select').addEventListener('change',event=>selectCase(event.target.value));$('version-select').addEventListener('change',event=>renderVersion(event.target.value));
  $('copy').addEventListener('click',async()=>{const text=[currentCase.title+'｜'+currentVersion.label,currentCase.synthetic?'合成数据演示':'',currentVersion.superseded?'历史方案已更正，请以最新版本决策。':'',...(currentVersion.takeaways.length?currentVersion.takeaways:[currentVersion.summary])].filter(Boolean).join('\n');
    try{if(!navigator.clipboard)throw new Error('Clipboard unavailable');await navigator.clipboard.writeText(text);toast('老板摘要已复制');}catch{ $('copy-fallback').hidden=false;$('copy-text').value=text;$('copy-text').focus();$('copy-text').select(); }});
  $('close-copy').addEventListener('click',()=>{$('copy-fallback').hidden=true;$('copy').focus();});
  $('print').addEventListener('click',()=>window.print());
  window.addEventListener('beforeprint',()=>{printDetails=[...document.querySelectorAll('details')].map(node=>({node,open:node.open}));printDetails.forEach(({node})=>node.open=true);});
  window.addEventListener('afterprint',()=>{printDetails.forEach(({node,open})=>node.open=open);printDetails=[];});
  const nav=[...document.querySelectorAll('nav a')];
  if('IntersectionObserver'in window){const observer=new IntersectionObserver(entries=>{entries.forEach(entry=>{if(entry.isIntersecting)nav.forEach(link=>link.classList.toggle('active',link.hash==='#'+entry.target.id));});},{rootMargin:'-15% 0px -65% 0px'});document.querySelectorAll('main>section').forEach(section=>observer.observe(section));}
  selectCase(currentCase.id);
})();
