/* Befragungsstudio: lokale Chartdarstellung, PNG- und ZIP-Export. */
(() => {
  'use strict';
  const payload = JSON.parse(document.getElementById('chart-data').textContent);
  const status = document.getElementById('export-status');
  const sizes = {wide: [1920, 1080], half: [960, 1080], compact: [1200, 900]};
  const charts = new Map();
  const fmt = (v, digits = 1) => new Intl.NumberFormat('de-CH', {maximumFractionDigits: digits, minimumFractionDigits: digits}).format(v);
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
  const valueLabels = {id: 'valueLabels', afterDatasetsDraw(chart, args, options) {
    const ctx = chart.ctx, ds = chart.data.datasets[0]; ctx.save(); ctx.fillStyle = '#18394f';
    ctx.font = `${options.fontSize || 13}px Arial, sans-serif`; ctx.textBaseline = 'middle';
    chart.getDatasetMeta(0).data.forEach((point, i) => {
      const v = ds.data[i]; if (v == null) return;
      const text = fmt(v, options.percent ? 1 : 2) + (options.percent ? ' %' : '');
      if (chart.config.type === 'line') {ctx.textAlign = 'center'; ctx.fillText(text, point.x, point.y - 22);}
      else {ctx.textAlign = 'left'; ctx.fillText(text, point.x + 9, point.y);}
    }); ctx.restore();
  }};

  function config(card, metric = 'mean', layout = 'screen', view = 'history') {
    const scale = card.rows[0].type === 'scale', latest = card.rows[card.rows.length - 1];
    const small = layout === 'half', exporting = layout !== 'screen', top = metric === 'top2';
    const fontSize = exporting ? (small ? 22 : 25) : 14;
    const labels = scale ? card.rows.map(r => wrap(`${r.wave} · n=${r.n}`, small ? 17 : 29))
      : Object.keys(latest.counts).map(s => wrap(s, small ? 22 : (exporting ? 38 : 35)));
    const values = scale ? card.rows.map(r => top ? r.top2 : r.mean)
      : Object.values(latest.counts).map(n => 100 * n / latest.n);
    const children = view === 'children';
    const datasets = [{label: scale ? payload.unit : 'Anteil (%)',
        ns:children ? card.children.map(r=>r.n) : card.rows.map(r=>r.n),
        data: children ? card.children.map(r => top ? r.top2 : r.mean) : values,
        borderColor:'#0070b4',backgroundColor:'#0070b4',borderWidth:3,
        pointRadius:exporting ? 7 : 5,pointHoverRadius:7,tension:0,maxBarThickness:30,
        showLine:!children}];
    if (scale && !children && document.getElementById('show-comparisons')?.checked !== false) {
      (card.comparisons || []).forEach((comp,i) => datasets.push({
        label:comp.label + (exporting ? ' · n=' + card.rows.map(row=>comp.rows.find(r=>r.wave===row.wave)?.n ?? '–').join('/') : ''),ns:card.rows.map(row=>comp.rows.find(r=>r.wave===row.wave)?.n),data:card.rows.map(row => {const r=comp.rows.find(r=>r.wave===row.wave);return r ? (top ? r.top2 : r.mean) : null;}),
        borderColor:['#ed8b23','#647887'][i%2],backgroundColor:['#ed8b23','#647887'][i%2],
        borderDash:[7,5],pointRadius:3,spanGaps:false
      }));
    }
    const chartLabels=children ? card.children.map(r=>wrap(`${r.unit} · n=${r.n}`,small?22:35)) : labels;
    return {
      type: scale && !children ? 'line' : 'bar',
      data: {labels:chartLabels,datasets},
      plugins: [whiteBackground, valueLabels],
      options: {
        indexAxis: scale && !children ? 'x' : 'y', responsive: !exporting, maintainAspectRatio: false,
        animation: false, devicePixelRatio: exporting ? 1 : Math.min(window.devicePixelRatio || 1, 2),
        layout: {padding: {top: 12, left: 12, right: exporting ? 115 : 85, bottom: 10}},
        plugins: {
          legend: {display: datasets.length>1,labels:{font:{size:fontSize}}},
          title: {display: exporting, text: [...(exporting ? [payload.project + ' · ' + payload.unit] : []),...wrap(card.wording || card.label, small ? 43 : (exporting ? 82 : 75))], color: '#172c3b',
            font: {family: 'Arial, sans-serif', size: exporting ? (small ? 27 : 32) : 19, weight: 'bold'}, padding: {bottom: exporting ? 30 : 20}},
          subtitle: {display: exporting, text: scale ? (top ? 'Zustimmungsanteil · gültige Antworten' : `Mittelwert · Skala ${latest.minimum}–${latest.maximum}`) + (children ? ` · ${latest.wave}` : '')
            : `${latest.wave} · n=${latest.n}` + (latest.type === 'choice_multiple' ? ' · Mehrfachnennungen möglich' : ''),
            font: {family: 'Arial, sans-serif', size: fontSize}, color: '#607381', padding: {bottom: 35}},
          tooltip: {enabled: !exporting,callbacks:{label:ctx=>`${ctx.dataset.label}: ${fmt(scale && !children ? ctx.parsed.y : ctx.parsed.x,top ? 1 : 2)}${top ? ' %' : ''} · n=${ctx.dataset.ns?.[ctx.dataIndex] ?? latest.n}`}}, valueLabels: {fontSize, percent: !scale || top}
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
  function draw(index) {
    const canvas = document.getElementById(`chart-${index}`);
    const metric = metricFor(index);
    if (charts.has(index)) charts.get(index).destroy();
    charts.set(index, new Chart(canvas, config(payload.cards[index], metric)));
    const childCanvas=document.getElementById(`children-${index}`);
    if(childCanvas){const key='child-'+index;if(charts.has(key))charts.get(key).destroy();charts.set(key,new Chart(childCanvas,config(payload.cards[index],metric,'screen','children')));}
  }
  async function png(index, layout, view = 'history') {
    if (document.fonts) await document.fonts.ready;
    const canvas = document.createElement('canvas'), size = sizes[layout];
    canvas.width = size[0]; canvas.height = size[1];
    const metric = metricFor(index);
    const cfg=config(payload.cards[index], metric, layout, view);
    const current=charts.get(index);
    if(view==='history' && current?.isDatasetVisible)cfg.data.datasets.forEach((ds,i)=>{ds.hidden=!current.isDatasetVisible(i);});
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
    return `${String(index + 1).padStart(2, '0')}_${label}_${metric}_${layout}_${view}.png`;
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
  async function start() {
    try {
      if (typeof Chart === 'undefined') throw new Error('Die eingebettete Chartbibliothek wurde nicht geladen.');
      Chart.defaults.font.family = 'Arial, sans-serif';
      payload.cards.forEach((card, i) => {draw(i); document.getElementById(`metric-${i}`)?.addEventListener('change', () => draw(i));});
      for (const id of ['report-metric','show-comparisons']) document.getElementById(id)?.addEventListener('change',()=>payload.cards.forEach((card,i)=>draw(i)));
      document.querySelectorAll('[data-png]').forEach(button => button.addEventListener('click', async () => {
        button.disabled = true;
        try {
          const i = Number(button.dataset.index), layout = button.dataset.png;
          download(await png(i, layout, button.dataset.view), filename(i, layout, button.dataset.view)); status.textContent = 'PNG erstellt.';
        } catch (error) {status.textContent = 'Export fehlgeschlagen: ' + error.message;}
        finally {button.disabled = false;}
      }));
      document.getElementById('all-charts').addEventListener('click', exportAll);
      status.textContent = `${payload.cards.length} Charts bereit. Darstellung und Export funktionieren offline.`;
      if (document.body.dataset.autoZip === 'true') await exportAll();
    } catch (error) {status.textContent = 'Charts konnten nicht geladen werden: ' + error.message;}
  }
  start();
})();
