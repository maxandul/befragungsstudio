// Test der Download-Orchestrierung mit Canvas-Testdouble; kein visueller Rendertest.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');

(async () => {
  const downloads = [], configured = [], events = {};
  const row = {type:'scale',wave:'2026',n:10,mean:4,top2:80,minimum:1,maximum:5};
  const payload = {project:'Test',unit:'Gesamt',cards:[{label:'Zufriedenheit',rows:[row]}]};
  const elements = {
    'chart-data': {textContent:JSON.stringify(payload)},
    'export-status': {textContent:''},
    'chart-0': {},
    'metric-0': {value:'top2',addEventListener(){}},
    'all-charts': {disabled:false,addEventListener(name,fn){events.all=fn;}}
  };
  const buttons = ['wide','half','compact'].map(layout => ({
    dataset:{png:layout,index:'0'},disabled:false,
    addEventListener(name,fn){events[layout]=fn;}
  }));
  const document = {
    fonts:{ready:Promise.resolve()},body:{dataset:{},appendChild(){}},
    getElementById:id=>elements[id],querySelectorAll:()=>buttons,
    createElement:tag=>tag==='canvas'
      ? {width:0,height:0,toBlob(fn){fn(new Blob([`PNG:${this.width}x${this.height}`],{type:'image/png'}));}}
      : {click(){},remove(){}}
  };
  class Chart {
    static defaults = {font:{}};
    constructor(canvas,config){configured.push({width:canvas.width,height:canvas.height,config});}
    update(){} destroy(){}
  }
  const sandbox={document,window:{devicePixelRatio:1},Chart,Intl,TextEncoder,Uint8Array,DataView,Blob,
    Map,Promise,requestAnimationFrame:fn=>fn(),setTimeout:()=>0,
    URL:{createObjectURL:blob=>{downloads.push(blob);return 'blob:test';},revokeObjectURL(){}}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/report-charts.js'),'utf8'),sandbox);
  assert.match(elements['export-status'].textContent,/1 Charts bereit/);
  for (const layout of ['wide','half','compact']) await events[layout]();
  assert.deepEqual(await Promise.all(downloads.map(blob=>blob.text())),[
    'PNG:1920x1080','PNG:960x1080','PNG:1200x900'
  ]);
  assert.equal(configured[1].config.data.datasets[0].data[0],80);
  assert.equal(configured[1].config.options.responsive,false);
  await events.all();
  assert.match(elements['export-status'].textContent,/3 PNG-Dateien als ZIP erstellt/);
  fs.writeFileSync(process.argv[2],Buffer.from(await downloads.at(-1).arrayBuffer()));
  console.log('Exportlayouts und ZIP-Orchestrierung geprüft.');
})().catch(error=>{console.error(error);process.exitCode=1;});
