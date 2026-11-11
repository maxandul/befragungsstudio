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
    ctx.font = `${options.fontSize || 13}px Arial`; ctx.textBaseline = 'middle';
    chart.getDatasetMeta(0).data.forEach((point, i) => {
      const v = ds.data[i]; if (v == null) return;
      const text = fmt(v, chart.config.type === 'line' ? 2 : 1) + (options.percent ? ' %' : '');
      if (chart.config.type === 'line') {ctx.textAlign = 'center'; ctx.fillText(text, point.x, point.y - 22);}
      else {ctx.textAlign = 'left'; ctx.fillText(text, point.x + 9, point.y);}
    }); ctx.restore();
  }};

  function config(card, metric = 'mean', layout = 'screen') {
    const scale = card.rows[0].type === 'scale', latest = card.rows[card.rows.length - 1];
    const small = layout === 'half', exporting = layout !== 'screen', top = metric === 'top2';
    const fontSize = exporting ? (small ? 22 : 25) : 14;
    const labels = scale ? card.rows.map(r => wrap(`${r.wave} · n=${r.n}`, small ? 17 : 29))
      : Object.keys(latest.counts).map(s => wrap(s, small ? 22 : (exporting ? 38 : 35)));
    const values = scale ? card.rows.map(r => top ? r.top2 : r.mean)
      : Object.values(latest.counts).map(n => 100 * n / latest.n);
    return {
      type: scale ? 'line' : 'bar',
      data: {labels, datasets: [{label: scale ? (top ? 'Zustimmung (%)' : 'Mittelwert') : 'Anteil (%)',
        data: values, borderColor: '#0070b4', backgroundColor: '#0070b4', borderWidth: scale ? 3 : 0,
        pointRadius: exporting ? 7 : 5, pointHoverRadius: 7, tension: 0, maxBarThickness: exporting ? 48 : 30}]},
      plugins: [whiteBackground, valueLabels],
      options: {
        indexAxis: scale ? 'x' : 'y', responsive: !exporting, maintainAspectRatio: false,
        animation: false, devicePixelRatio: exporting ? 1 : Math.min(window.devicePixelRatio || 1, 2),
        layout: {padding: {top: 12, left: 12, right: exporting ? 115 : 85, bottom: 10}},
        plugins: {
          legend: {display: false},
          title: {display: true, text: [payload.project + ' · ' + payload.unit + (payload.focus_wave ? ' · Bezugswelle ' + payload.focus_wave : ''),
            ...wrap(card.label, small ? 43 : (exporting ? 82 : 75))], color: '#172c3b',
            font: {family: 'Arial', size: exporting ? (small ? 27 : 32) : 19, weight: 'bold'}, padding: {bottom: exporting ? 30 : 20}},
          subtitle: {display: true, text: scale ? (top ? 'Zustimmungsanteil · gültige Antworten' : `Mittelwert · Skala ${latest.minimum}–${latest.maximum}`)
            : `${latest.wave} · n=${latest.n}` + (latest.type === 'choice_multiple' ? ' · Mehrfachnennungen möglich' : ''),
            font: {family: 'Arial', size: fontSize}, color: '#607381', padding: {bottom: 35}},
          tooltip: {enabled: !exporting}, valueLabels: {fontSize, percent: !scale || top}
        },
        scales: {
          x: {min: scale ? undefined : 0, max: scale ? undefined : 100,
            grid: {display: !scale, color: '#edf1f5'}, border: {display: false},
            ticks: {font: {family: 'Arial', size: fontSize}, color: '#455c6c', maxRotation: 0, autoSkip: false}},
          y: {min: scale ? (top ? 0 : latest.minimum) : undefined, max: scale ? (top ? 100 : latest.maximum) : undefined,
            grid: {display: scale, color: '#edf1f5'}, border: {display: false},
            ticks: {font: {family: 'Arial', size: fontSize}, color: '#455c6c', autoSkip: false}}
        }
      }
    };
  }
  function draw(index) {
    const canvas = document.getElementById(`chart-${index}`);
    const metric = document.getElementById(`metric-${index}`)?.value || 'mean';
    if (charts.has(index)) charts.get(index).destroy();
    charts.set(index, new Chart(canvas, config(payload.cards[index], metric)));
  }
  async function png(index, layout) {
    if (document.fonts) await document.fonts.ready;
    const canvas = document.createElement('canvas'), size = sizes[layout];
    canvas.width = size[0]; canvas.height = size[1];
    const metric = document.getElementById(`metric-${index}`)?.value || 'mean';
    const chart = new Chart(canvas, config(payload.cards[index], metric, layout));
    try {
      chart.update('none');
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
      if (!blob) throw new Error('PNG konnte nicht erstellt werden.');
      return blob;
    } finally { chart.destroy(); }
  }
  function filename(index, layout) {
    const metric = document.getElementById(`metric-${index}`)?.value || 'mean';
    const label = payload.cards[index].label.replace(/[^a-zA-Z0-9äöüÄÖÜ_-]+/g, '_').slice(0, 70);
    return `${String(index + 1).padStart(2, '0')}_${label}_${metric}_${layout}.png`;
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
      Chart.defaults.font.family = 'Arial';
      payload.cards.forEach((card, i) => {draw(i); document.getElementById(`metric-${i}`)?.addEventListener('change', () => draw(i));});
      document.querySelectorAll('[data-png]').forEach(button => button.addEventListener('click', async () => {
        button.disabled = true;
        try {
          const i = Number(button.dataset.index), layout = button.dataset.png;
          download(await png(i, layout), filename(i, layout)); status.textContent = 'PNG erstellt.';
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
