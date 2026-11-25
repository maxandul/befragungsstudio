/* Befragungsstudio: lokale Chartdarstellung, PNG- und ZIP-Export. */
(() => {
  'use strict';
  const payload = JSON.parse(document.getElementById('chart-data').textContent);
  const status = document.getElementById('export-status');
  const sizes = {wide: [1920, 1080], half: [960, 1080], compact: [1200, 900]};
  const charts = new Map();
  // Die Auswahl der Legende bleibt bei Metrik- und Vergleichswechseln erhalten.
  const visibility = new Map();
  function rememberVisibility(key) {
    const chart=charts.get(key);
    if (!chart?.isDatasetVisible || !chart.data) return;
    const state=visibility.get(key) || new Map();
    chart.data.datasets.forEach((ds,i)=>state.set(ds.id || ds.label,chart.isDatasetVisible(i)));
    visibility.set(key,state);
  }
  function applyVisibility(key,cfg) {
    const state=visibility.get(key);
    cfg.data.datasets.forEach(ds=>{if(state?.has(ds.id || ds.label))ds.hidden=!state.get(ds.id || ds.label);});
    return cfg;
  }
  function comparisonVisible(comp) {
    return document.getElementById('show-comparisons')?.checked !== false &&
      document.getElementById(`show-${comp.kind || 'total'}`)?.checked !== false;
  }
  const fmt = (v, digits = 1) => new Intl.NumberFormat('de-CH', {maximumFractionDigits: digits, minimumFractionDigits: digits}).format(v);
  const agreementLabel = row => row.minimum===1 && row.maximum===5 && (row.top_from ?? 4)===4
    ? 'Zustimmung: Antworten 4 und 5' : `Zustimmung: Antworten ab ${row.top_from ?? 4}`;
  const intervalsEnabled = () => document.getElementById('show-ci')?.checked === true;
  function wrap(text, width) {
    const lines = []; let line = '';
    for (const word of String(text).split(/\s+/)) {
      if (line && line.length + word.length + 1 > width) {lines.push(line); line = '';}
      line += (line ? ' ' : '') + word;
    }
    if (line) lines.push(line);
    return lines;
  }
  const whiteBackground = {id: 'whiteBackground', beforeDraw(chart) {
    const ctx = chart.ctx; ctx.save(); ctx.globalCompositeOperation = 'destination-over';
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, chart.width, chart.height); ctx.restore();
  }};
  const confidenceIntervals = {id:'confidenceIntervals',afterDatasetsDraw(chart,args,options) {
    if(!options.enabled || !chart.isDatasetVisible(0))return;
    const ctx=chart.ctx, area=chart.chartArea, ds=chart.data.datasets[0];
    const axis=options.horizontal ? chart.scales.x : chart.scales.y;
    const cap=options.exporting ? 7 : 4;
    ctx.save();ctx.beginPath();
    if(options.horizontal)ctx.rect(area.left,area.top-cap,area.right-area.left,area.bottom-area.top+2*cap);
    else ctx.rect(area.left-cap,area.top,area.right-area.left+2*cap,area.bottom-area.top);
    ctx.clip();ctx.strokeStyle='#243746';ctx.lineWidth=options.exporting ? 3 : 1.5;
    chart.getDatasetMeta(0).data.forEach((point,i)=>{
      const ci=ds.ci95?.[i];
      if(!ci || !ci.every(Number.isFinite) || ds.data[i]==null)return;
      const low=axis.getPixelForValue(ci[0]), high=axis.getPixelForValue(ci[1]);
      ctx.beginPath();
      if(options.horizontal){ctx.moveTo(low,point.y);ctx.lineTo(high,point.y);ctx.moveTo(low,point.y-cap);ctx.lineTo(low,point.y+cap);ctx.moveTo(high,point.y-cap);ctx.lineTo(high,point.y+cap);}
      else{ctx.moveTo(point.x,low);ctx.lineTo(point.x,high);ctx.moveTo(point.x-cap,low);ctx.lineTo(point.x+cap,low);ctx.moveTo(point.x-cap,high);ctx.lineTo(point.x+cap,high);}
      ctx.stroke();
    });ctx.restore();
  }};
  const comparisonLines={id:'comparisonLines',afterDatasetsDraw(chart,args,options){
    if(!options.enabled)return;
    chart.data.datasets.forEach((ds,i)=>{
      if(i===0 || !chart.isDatasetVisible(i))return;
      const value=ds.data.find(Number.isFinite);if(value===undefined)return;
      const x=chart.scales.x.getPixelForValue(value),area=chart.chartArea;
      if(x<area.left || x>area.right)return;
      const ctx=chart.ctx;ctx.save();ctx.strokeStyle=ds.borderColor;ctx.lineWidth=1.5;
      ctx.setLineDash(ds.borderDash || []);ctx.beginPath();ctx.moveTo(x,area.top);ctx.lineTo(x,area.bottom);ctx.stroke();ctx.restore();
    });
  }};
  const valueLabels = {id: 'valueLabels', afterDatasetsDraw(chart, args, options) {
    if (chart.isDatasetVisible && !chart.isDatasetVisible(0)) return;
    const ctx = chart.ctx, ds = chart.data.datasets[0]; ctx.save(); ctx.fillStyle = '#18394f';
    ctx.font = `${options.fontSize || 13}px Arial, sans-serif`; ctx.textBaseline = 'middle';
    chart.getDatasetMeta(0).data.forEach((point, i) => {
      const entry = ds.data[i], v = entry && typeof entry === 'object' ? entry.x : entry; if (v == null) return;
      const text = fmt(v, options.percent ? 1 : 2) + (options.percent ? ' %' : '') + (ds.completePopulation?.[i] ? '*' : '');
      const ci=chart.options.plugins.confidenceIntervals?.enabled ? ds.ci95?.[i] : null;
      if (chart.config.type === 'line') {ctx.textAlign = 'center';const y=ci ? Math.max(chart.chartArea.top+8,chart.scales.y.getPixelForValue(ci[1])-14) : point.y-22;ctx.fillText(text,point.x,y);}
      else {ctx.textAlign = 'left';const x=ci ? Math.min(chart.chartArea.right,chart.scales.x.getPixelForValue(ci[1]))+9 : point.x+9;ctx.fillText(text,x,point.y);}
    }); ctx.restore();
  }};
  const completeMarkers={id:'completeMarkers',afterDatasetsDraw(chart){
    const ctx=chart.ctx;ctx.save();ctx.font='bold 16px Arial, sans-serif';
    chart.data.datasets.forEach((ds,k)=>{
      if((k===0 && chart.options.plugins.valueLabels!==false) || !chart.isDatasetVisible(k))return;
      ctx.fillStyle=ds.borderColor;
      chart.getDatasetMeta(k).data.forEach((point,i)=>{
        const value=ds.data[i];
        if(ds.completePopulation?.[i] && value!=null && (typeof value!=='object' || value.x!=null))
          ctx.fillText('*',point.x+10,point.y-10);
      });
    });ctx.restore();
  }};

  function config(card, metric = 'mean', layout = 'screen', view = 'history') {
    const scale = card.rows[0].type === 'scale', latest = card.rows[card.rows.length - 1];
    const small = layout === 'half', exporting = layout !== 'screen', top = metric === 'top2';
    const manyOptions=!scale && Object.keys(latest.counts).length>10;
    const fontSize = exporting ? (manyOptions ? (small ? 14 : 18) : (small ? 22 : 25)) : 14;
    const options=Object.entries(latest.counts || {}).sort((a,b)=>b[1]-a[1] || a[0].localeCompare(b[0],'de'));
    const labels = scale ? card.rows.map(r => wrap(`${r.wave} · n=${r.n}`, small ? 17 : 29))
      : options.map(([s]) => wrap(s, manyOptions ? (small ? 37 : 60) : (small ? 22 : (exporting ? 38 : 35))));
    const values = scale ? card.rows.map(r => top ? r.top2 : r.mean)
      : options.map(([,n]) => 100 * n / latest.n);
    const children = view === 'children';
    const showCI=scale && intervalsEnabled(), intervalKey=top ? 'top2_ci95' : 'mean_ci95';
    const datasets = [{id:'selected',label: scale ? payload.unit : 'Anteil (%)',
        completePopulation:(children ? card.children : card.rows).map(r=>!!r.complete_population),
        ci95:(children ? card.children : card.rows).map(r=>r[intervalKey] || null),
        ns:children ? card.children.map(r=>r.n) : card.rows.map(r=>r.n),
        data: children ? card.children.map(r => top ? r.top2 : r.mean) : values,
        borderColor:'#0070b4',backgroundColor:'#0070b4',borderWidth:3,
        pointRadius:exporting ? 7 : 5,pointHoverRadius:7,tension:0,maxBarThickness:30,
        showLine:!children}];
    if (scale && document.getElementById('show-comparisons')?.checked !== false) {
      (card.comparisons || []).filter(comparisonVisible).forEach(comp => datasets.push({id:comp.kind || comp.label,
        label:comp.label + (exporting ? ' · n=' + (children ? [latest] : card.rows).map(row=>comp.rows.find(r=>r.wave===row.wave)?.n ?? '–').join('/') : ''),
        ns:(children ? card.children : card.rows).map(row=>comp.rows.find(r=>r.wave===(children ? latest.wave : row.wave))?.n),
        completePopulation:(children ? card.children : card.rows).map(row=>!!comp.rows.find(r=>r.wave===(children ? latest.wave : row.wave))?.complete_population),
        data:(children ? card.children : card.rows).map(row=>{const r=comp.rows.find(r=>r.wave===(children ? latest.wave : row.wave));return r ? (top ? r.top2 : r.mean) : null;}),
        type:'line',indexAxis:children ? 'y' : 'x',showLine:!children,
        borderColor:comp.kind==='total' ? '#647887' : '#ed8b23',backgroundColor:comp.kind==='total' ? '#647887' : '#ed8b23',
        borderWidth:1.5,borderDash:[7,5],pointStyle:'line',pointRadius:children ? 0 : 3,spanGaps:false
      }));
    }
    const chartLabels=children ? card.children.map(r=>wrap(`${r.unit} · n=${r.n}`,small?22:35)) : labels;
    return {
      type: scale && !children ? 'line' : 'bar',
      data: {labels:chartLabels,datasets},
      plugins: [whiteBackground, confidenceIntervals, comparisonLines, valueLabels, completeMarkers],
      options: {
        indexAxis: scale && !children ? 'x' : 'y', responsive: !exporting, maintainAspectRatio: false,
        animation: false, devicePixelRatio: exporting ? 1 : Math.min(window.devicePixelRatio || 1, 2),
        layout: {padding: {top: 12, left: 12, right: exporting ? 115 : 85, bottom: 10}},
        plugins: {
          legend: {display: datasets.length>1,labels:{usePointStyle:true,pointStyle:'line',pointStyleWidth:28,boxHeight:2,padding:18,font:{size:fontSize}}},
          title: {display: exporting, text: [...(exporting ? [payload.project + ' · ' + payload.unit] : []),...wrap(card.wording || card.label, small ? 43 : (exporting ? 82 : 75))], color: '#172c3b',
            font: {family: 'Arial, sans-serif', size: exporting ? (small ? 27 : 32) : 19, weight: 'bold'}, padding: {bottom: exporting ? 30 : 20}},
          subtitle: {display: exporting || !scale || showCI, text: wrap((scale ? (top ? agreementLabel(latest)+' · gültige Antworten' : `Mittelwert · Skala ${latest.minimum}–${latest.maximum}`) + (children ? ` · ${latest.wave}` : '')
            : `${latest.wave} · n=${latest.n}` + (latest.type === 'choice_multiple' ? ' · Mehrfachnennungen möglich' : '')) + (showCI ? ` · 95%-KI (${top ? 'Wilson' : 't'})${children ? ' je Einheit' : ' der ausgewählten OE'}` : ''),small ? 48 : 100).concat(showCI && exporting ? wrap('Modellbasiert; Nichtteilnahme nicht abgebildet.',small ? 48 : 100) : []),
            font: {family: 'Arial, sans-serif', size: fontSize}, color: '#607381', padding: {bottom: 35}},
          confidenceIntervals:{enabled:showCI,horizontal:children,exporting},comparisonLines:{enabled:children},
          tooltip: {enabled: !exporting,callbacks:{label:ctx=>{
            const complete=ctx.dataset.completePopulation?.[ctx.dataIndex];
            const label=`${ctx.dataset.label}: ${fmt(scale && !children ? ctx.parsed.y : ctx.parsed.x,top ? 1 : 2)}${top || !scale ? ' %' : ''}${complete ? '*' : ''} · n=${ctx.dataset.ns?.[ctx.dataIndex] ?? latest.n}`;
            if(!showCI || ctx.datasetIndex!==0 || complete)return label;
            const ci=ctx.dataset.ci95?.[ctx.dataIndex];
            return [label,ci ? `95%-KI: ${fmt(ci[0],top ? 1 : 2)}–${fmt(ci[1],top ? 1 : 2)}${top ? ' %' : ''}` : '95%-KI nicht berechenbar'];
          }}}, valueLabels: {fontSize, percent: !scale || top}
        },
        scales: {
          x: {min: children ? (top ? 0 : latest.minimum) : (scale ? undefined : 0), max: children ? (top ? 100 : latest.maximum) : (scale ? undefined : 100),
            grid: {display: !scale || children, color: '#edf1f5'}, border: {display: false},
            ticks: {font: {family: 'Arial, sans-serif', size: fontSize}, color: '#455c6c', maxRotation: 0, autoSkip: false, stepSize:children ? (top ? 20 : 1) : undefined}},
          y: {min: scale && !children ? (top ? 0 : latest.minimum) : undefined, max: scale && !children ? (top ? 100 : latest.maximum) : undefined,
            grid: {display: scale && !children, color:context=>Number.isInteger(context.tick?.value) ? '#dde5ec' : '#f1f4f7'}, border: {display: false},
            ticks: {font: {family: 'Arial, sans-serif', size: fontSize}, color: '#455c6c', autoSkip: false,stepSize:scale && !children ? (top ? 20 : 0.5) : undefined,callback:scale && !children ? (top ? value=>value : value=>Number.isInteger(value)?value:'') : function(value){return this.getLabelForValue(value);}}}
        }
      }
    };
  }
  function metricFor(index) {return document.getElementById('report-metric')?.value || document.getElementById(`metric-${index}`)?.value || 'mean';}
  const palette = ['#0070b4','#d16a00','#667b35','#8d57a1','#a34354','#247f78','#586778','#9b7710'];
  function overviewConfig(index, view, exporting = false) {
    const overview = payload.overviews[index], cards = overview.indices.map(i => payload.cards[i]);
    const top = metricFor(overview.indices[0]) === 'top2';
    // Rotated squares and triangles extend beyond their radius at scale endpoints.
    // Explicit scale limits otherwise cause Chart.js to clip them at the axis.
    const markerPadding=Math.ceil((exporting ? 9 : 6)*Math.SQRT2+3);
    const series = view === 'history' ? [...payload.selected].reverse().map(wave=>({id:'wave-'+wave,label:wave,
        rows:cards.map(card=>card.rows.find(r=>r.wave===wave))}))
      : [{id:'selected',label:payload.unit,rows:cards.map(card=>card.rows.find(r=>r.wave===overview.reference_wave))},
        ...[...new Set(cards.flatMap(c=>c.children.map(r=>r.unit)))].map(unit=>({id:'child-'+unit,label:unit,
          rows:cards.map(card=>card.children.find(r=>r.unit===unit && r.wave===overview.reference_wave))})),
        ...[...new Map(cards.flatMap(c=>(c.comparisons || []).filter(comparisonVisible)).map(comp=>[comp.kind || comp.label,comp])).values()]
          .map(comp=>({id:comp.kind || comp.label,label:comp.label,comparison:true,
            rows:cards.map(card=>(card.comparisons || []).find(c=>(c.kind || c.label)===(comp.kind || comp.label))?.rows.find(r=>r.wave===overview.reference_wave))}))];
    const rows=series.map(s=>s.rows);
    const labels = cards.map((card, i) => [
      ...wrap(exporting ? card.wording || card.label : card.label, exporting ? 58 : 34),
      ...(exporting ? wrap('n: ' + rows.map(rs => rs[i]?.n ?? '–').join(' / '), 58) : [])
    ]);
    return {
      type:'scatter', plugins:[whiteBackground, valueLabels, completeMarkers],
      data:{labels,datasets:series.map((item,k) => ({id:item.id,label:item.label, ns:rows[k].map(r => r?.n),
        clip:{left:markerPadding,right:markerPadding,top:markerPadding,bottom:markerPadding},
        completePopulation:rows[k].map(r=>!!r?.complete_population),
        data:rows[k].map((r,i) => ({x:r ? (top ? r.top2 : r.mean) : null,y:i})),
        borderColor:item.comparison ? (item.id==='parent' ? '#883e96' : '#485865') : palette[k % palette.length],
        backgroundColor:item.comparison ? (item.id==='parent' ? '#883e96' : '#485865') : palette[k % palette.length],
        pointStyle:item.comparison ? (item.id==='parent' ? 'rectRot' : 'triangle') : ['circle','rectRot','triangle','rect','crossRot','star','cross','dash'][k % 8],
        pointRadius:exporting ? (k === 0 ? 9 : 7) : (k === 0 ? 6 : 5),showLine:false}))},
      options:{responsive:!exporting,maintainAspectRatio:false,animation:false,
        devicePixelRatio:exporting ? 1 : Math.min(window.devicePixelRatio || 1,2),
        layout:{padding:{top:markerPadding,left:markerPadding,right:28,bottom:markerPadding}},
        plugins:{legend:{position:'bottom',labels:{font:{size:exporting ? 21 : 13},usePointStyle:true}},
          title:{display:exporting,text:[...wrap(payload.project+' · '+payload.unit,85),...wrap(overview.theme,85)],font:{size:30},color:'#172c3b'},
          subtitle:{display:true,text:[view === 'history' ? 'Zeitvergleich' : 'OE-Vergleich · '+overview.reference_wave,
            top ? 'Zustimmung (%)' : `Mittelwert · Skala ${overview.minimum}–${overview.maximum}`,
            ...(exporting ? ['n je Frage in Reihenfolge der Legende · – = kein freigegebenes Ergebnis'] : [])],font:{size:exporting ? 20 : 13}},
          valueLabels:false,
          tooltip:{enabled:!exporting,callbacks:{title:items => cards[items[0].dataIndex].wording || cards[items[0].dataIndex].label,
            label:ctx => `${ctx.dataset.label}: ${fmt(ctx.parsed.x,top ? 1 : 2)}${top ? ' %' : ''}${ctx.dataset.completePopulation?.[ctx.dataIndex] ? '*' : ''} · n=${ctx.dataset.ns[ctx.dataIndex]}`}}},
        scales:{x:{min:top ? 0 : overview.minimum,max:top ? 100 : overview.maximum,
          ticks:{stepSize:top ? 20 : 1,font:{size:exporting ? 23 : 14}},grid:{color:'#e2e9ef'}},
          y:{type:'category',labels,reverse:false,offset:true,grid:{color:'#edf1f5'},
            ticks:{autoSkip:false,font:{size:exporting ? 23 : 13}}}}
      }
    };
  }
  function drawOverviews() {
    (payload.overviews || []).forEach((overview,i) => {
      for (const view of ['history','children']) {
        const key=`overview-${view}-${i}`, canvas=document.getElementById(key);
        if (!canvas) continue;
        rememberVisibility(key);charts.get(key)?.destroy();
        charts.set(key,new Chart(canvas,applyVisibility(key,overviewConfig(i,view))));
      }
    });
  }
  async function topicPng(index, view) {
    if (document.fonts) await document.fonts.ready;
    const canvas=document.createElement('canvas');canvas.width=1920;canvas.height=1080;
    const cfg=overviewConfig(index,view,true), current=charts.get(`overview-${view}-${index}`);
    cfg.data.datasets.forEach((ds,i)=>{if(current?.isDatasetVisible)ds.hidden=!current.isDatasetVisible(i);});
    const chart=new Chart(canvas,cfg);
    try {
      chart.update('none');
      const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
      if(!blob)throw new Error('Themen-PNG konnte nicht erstellt werden.');
      return blob;
    } finally {chart.destroy();}
  }
  function topicFilename(index,view) {
    const overview=payload.overviews[index], label=overview.theme.replace(/[^a-zA-Z0-9äöüÄÖÜ_-]+/g,'_').slice(0,60);
    return `Thema_${index+1}_${label}_${metricFor(overview.indices[0])}_${view}.png`;
  }
  const questionSections = new Map();
  function releaseChart(key) {
    const chart=charts.get(key);
    if (!chart) return;
    rememberVisibility(key);
    chart.destroy();
    charts.delete(key);
  }
  function draw(index) {
    releaseChart(index);
    releaseChart('child-'+index);
    const metric = metricFor(index);
    const canvas = document.getElementById(`chart-${index}`);
    charts.set(index, new Chart(canvas, applyVisibility(index,config(payload.cards[index], metric))));
    const childCanvas=document.getElementById(`children-${index}`);
    if (childCanvas) {
      const key='child-'+index;
      charts.set(key,new Chart(childCanvas,applyVisibility(key,config(payload.cards[index],metric,'screen','children'))));
    }
  }
  function syncSection(detail, full=true) {
    for (const index of questionSections.get(detail) || []) {
      if (!detail.open) {
        releaseChart(index);
        releaseChart('child-'+index);
      } else if (!charts.has(index) && (full || payload.cards[index].rows[0].type!=='scale')) {
        draw(index);
      }
    }
  }
  function redrawOpenQuestions() {
    for (let i=0;i<payload.cards.length;i++) {
      if (charts.has(i)) draw(i);
    }
  }
  async function png(index, layout, view = 'history') {
    if (document.fonts) await document.fonts.ready;
    const canvas = document.createElement('canvas'), size = sizes[layout];
    canvas.width = size[0]; canvas.height = size[1];
    const metric = metricFor(index);
    const key=view==='children' ? 'child-'+index : index;
    rememberVisibility(key);
    const cfg=applyVisibility(key,config(payload.cards[index], metric, layout, view));
    const chart = new Chart(canvas, cfg);
    try {
      chart.update('none');
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
      if (!blob) throw new Error('PNG konnte nicht erstellt werden.');
      return blob;
    } finally { chart.destroy(); }
  }
  function filename(index, layout, view = 'history') {
    const metric = metricFor(index);
    const label = payload.cards[index].label.replace(/[^a-zA-Z0-9äöüÄÖÜ_-]+/g, '_').slice(0, 70);
    const ci=intervalsEnabled() && payload.cards[index].rows[0].type==='scale' ? '_ci95' : '';
    return `${String(index + 1).padStart(2, '0')}_${label}_${metric}_${layout}_${view}${ci}.png`;
  }
  function download(blob, name) {
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = name; document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  }
  // PNGs sind bereits komprimiert; ZIP speichert sie ohne weitere Kompression.
  function zip(files) {
    const encoder = new TextEncoder(), local = [], central = []; let offset = 0;
    const crc = bytes => {
      let c = 0xffffffff;
      for (const byte of bytes) {c ^= byte; for (let i = 0; i < 8; i++) c = (c >>> 1) ^ ((c & 1) ? 0xedb88320 : 0);}
      return (c ^ 0xffffffff) >>> 0;
    };
    const make = n => {const bytes = new Uint8Array(n); return [bytes, new DataView(bytes.buffer)];};
    for (const file of files) {
      const name = encoder.encode(file.name), bytes = file.bytes, checksum = crc(bytes);
      const [header, h] = make(30);
      h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x800, true);
      h.setUint32(14, checksum, true); h.setUint32(18, bytes.length, true);
      h.setUint32(22, bytes.length, true); h.setUint16(26, name.length, true);
      local.push(header, name, bytes);
      const [directory, d] = make(46);
      d.setUint32(0, 0x02014b50, true); d.setUint16(4, 20, true); d.setUint16(6, 20, true);
      d.setUint16(8, 0x800, true); d.setUint32(16, checksum, true);
      d.setUint32(20, bytes.length, true); d.setUint32(24, bytes.length, true);
      d.setUint16(28, name.length, true); d.setUint32(42, offset, true);
      central.push(directory, name); offset += header.length + name.length + bytes.length;
    }
    const centralSize = central.reduce((n, b) => n + b.length, 0), [end, e] = make(22);
    e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true);
    e.setUint32(12, centralSize, true); e.setUint32(16, offset, true);
    return new Blob([...local, ...central, end], {type: 'application/zip'});
  }
  let busy = false;
  async function exportAll() {
    if (busy) return; busy = true;
    const button = document.getElementById('all-charts'); button.disabled = true;
    try {
      const files = [];
      for (let i=0;i<(payload.overviews || []).length;i++) {
        for(const view of ['history','children']) {
          if(!document.getElementById(`overview-${view}-${i}`))continue;
          status.textContent=`Erstelle Themenübersicht ${i+1} …`;
          await new Promise(resolve=>requestAnimationFrame(resolve));
          const blob=await topicPng(i,view);
          files.push({name:topicFilename(i,view),bytes:new Uint8Array(await blob.arrayBuffer())});
        }
      }
      for (let i = 0; i < payload.cards.length; i++) {
        status.textContent = `Erstelle Charts: ${i + 1} von ${payload.cards.length} …`;
        await new Promise(resolve => requestAnimationFrame(resolve));
        for (const layout of Object.keys(sizes)) {
          const blob = await png(i, layout);
          files.push({name: filename(i, layout), bytes: new Uint8Array(await blob.arrayBuffer())});
          if (payload.cards[i].children?.length && payload.cards[i].rows[0].type==='scale') {
            const childBlob=await png(i,layout,'children');
            files.push({name:filename(i,layout,'children'),bytes:new Uint8Array(await childBlob.arrayBuffer())});
          }
        }
      }
      if (!files.length) {status.textContent = 'Keine freigegebenen Charts vorhanden.'; return;}
      download(zip(files), 'Charts.zip'); status.textContent = `${files.length} PNG-Dateien als ZIP erstellt.`;
    } catch (error) {status.textContent = 'Export fehlgeschlagen: ' + error.message;}
    finally {busy = false; button.disabled = false;}
  }
  let printDetails=[],printImages=[];
  function finishPrint() {
    printImages.forEach(img=>{img.parentElement?.classList.remove('print-chart-ready');img.remove();});printImages=[];
    printDetails.forEach(([detail,open])=>{detail.open=open;detail.classList.remove('print-hide');syncSection(detail);});printDetails=[];
    charts.forEach(chart=>{chart.resize();chart.update('none');});
  }
  function preparePrint() {
    if(printDetails.length || printImages.length)return;
    const full=document.body.dataset.profile==='oe' || document.body.dataset.printMode==='full';
    document.querySelectorAll('.question-details,.methodology').forEach(detail=>{
      printDetails.push([detail,detail.open]);
      const isMethod=detail.classList.contains('methodology');
      const hasChoice=detail.querySelector('article:not([data-question-type="scale"])');
      detail.open=isMethod || full || Boolean(hasChoice);
      if(!detail.open)detail.classList.add('print-hide');
      if(detail.open)syncSection(detail,full);
    });
    charts.forEach((chart,key)=>{
      const canvas=chart.canvas;if(!canvas)return;
      if(!full && canvas.closest('article[data-question-type="scale"]'))return;
      const height=String(key).startsWith('overview-') ? 510 : 416;
      chart.resize(700,height);chart.update('none');
      const img=document.createElement('img');img.className='print-chart-image';
      img.alt=canvas.getAttribute('aria-label') || 'Diagramm';img.src=canvas.toDataURL('image/png');
      canvas.parentElement.appendChild(img);canvas.parentElement.classList.add('print-chart-ready');printImages.push(img);
    });
  }
  window.addEventListener?.('beforeprint',preparePrint);
  window.addEventListener?.('afterprint',finishPrint);
  async function start() {
    try {
      if (typeof Chart === 'undefined') throw new Error('Die eingebettete Chartbibliothek wurde nicht geladen.');
      Chart.defaults.font.family = 'Arial, sans-serif';
      payload.cards.forEach((card, i) => {
        const section=document.getElementById(`chart-${i}`).closest('.question-details');
        if (section) {
          if (!questionSections.has(section)) {
            questionSections.set(section,[]);
            section.addEventListener('toggle',()=>syncSection(section));
          }
          questionSections.get(section).push(i);
        }
        if (!section || section.open) draw(i);
        document.getElementById(`metric-${i}`)?.addEventListener('change', () => {
          if (charts.has(i)) draw(i);
        });
      });
      drawOverviews();
      for (const id of ['report-metric','show-comparisons','show-parent','show-total']) document.getElementById(id)?.addEventListener('change',()=>{redrawOpenQuestions();drawOverviews();});
      document.getElementById('show-ci')?.addEventListener('change',()=>{
        redrawOpenQuestions();
        const note=document.getElementById('ci-note');if(note)note.hidden=!intervalsEnabled();
      });
      document.querySelectorAll('[data-topic]').forEach(button=>button.addEventListener('click',async()=>{
        button.disabled=true;
        try {const i=Number(button.dataset.topic),view=button.dataset.topicView;download(await topicPng(i,view),topicFilename(i,view));status.textContent='Themen-PNG erstellt.';}
        catch(error){status.textContent='Export fehlgeschlagen: '+error.message;}
        finally{button.disabled=false;}
      }));
      document.querySelectorAll('[data-png]').forEach(button => button.addEventListener('click', async () => {
        button.disabled = true;
        try {
          const i = Number(button.dataset.index), layout = button.dataset.png;
          download(await png(i, layout, button.dataset.view), filename(i, layout, button.dataset.view)); status.textContent = 'PNG erstellt.';
        } catch (error) {status.textContent = 'Export fehlgeschlagen: ' + error.message;}
        finally {button.disabled = false;}
      }));
      document.getElementById('all-charts').addEventListener('click', exportAll);
      const printButton=document.getElementById('report-print');if(printButton)printButton.disabled=false;
      status.textContent = '';
      if (document.body.dataset.autoZip === 'true') await exportAll();
    } catch (error) {status.textContent = 'Charts konnten nicht geladen werden: ' + error.message;}
  }
  start();
})();
