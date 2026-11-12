// Konfigurations- und Downloadprüfung; kein Browser-Layouttest.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
  const configurations=[],downloads=[],events={};
  const row=(wave,mean,n=5)=>({type:'scale',minimum:1,maximum:5,wave,mean,top2:mean*20,n});
  const payload={project:'Test',unit:'Bereich',selected:['2024','2026'],reference_wave:'2026',
    cards:[{label:'Frage A',wording:'Vollständiger Wortlaut A',rows:[row('2024',3),row('2026',4)],children:[{unit:'Team',...row('2026',5)}]},
      {label:'Frage B',wording:'Vollständiger Wortlaut B',rows:[row('2024',2)],children:[]}],
    overviews:[{theme:'Thema',indices:[0,1],minimum:1,maximum:5,reference_wave:'2026'}]};
  payload.cards[0].comparisons=[{kind:'parent',label:'Übergeordnete OE: Amt',rows:[row('2026',3.5,20)]},
    {kind:'total',label:'Test · gesamt',rows:[row('2026',3.8,30)]}];
  payload.cards[1].comparisons=[{kind:'parent',label:'Übergeordnete OE: Amt',rows:[row('2024',3,20)]}];
  const elements={'chart-data':{textContent:JSON.stringify(payload)},'export-status':{},
    'report-metric':{value:'mean',addEventListener(name,fn){events.metric=fn;}},
    'all-charts':{addEventListener(){}},'chart-0':{},'chart-1':{},
    'overview-history-0':{},'overview-children-0':{}};
  for(const kind of ['parent','total'])elements['show-'+kind]={checked:true,addEventListener(name,fn){events[kind]=fn;}};
  const button={dataset:{topic:'0',topicView:'children'},addEventListener(name,fn){events.png=fn;}};
  class Chart {
    static defaults={font:{}};
    constructor(canvas,config){this.data=config.data;configurations.push({canvas,config});}
    isDatasetVisible(i){return !this.data.datasets[i].hidden && i!==1;} // Manuell ausgeblendete Einheit.
    destroy(){}update(){}
  }
  const document={getElementById:id=>elements[id],fonts:{ready:Promise.resolve()},body:{dataset:{},appendChild(){}},
    querySelectorAll:selector=>selector==='[data-topic]'?[button]:[],
    createElement:tag=>tag==='canvas'?{toBlob(fn){fn(new Blob(['PNG']));}}:{click(){},remove(){}}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/report-charts.js'),'utf8'),{
    document,Chart,window:{devicePixelRatio:1},Intl,Map,Promise,Blob,setTimeout:()=>0,
    URL:{createObjectURL:b=>{downloads.push(b);return 'blob:test';},revokeObjectURL(){}}
  });
  const overview=view=>configurations.filter(c=>c.canvas===elements[`overview-${view}-0`]).at(-1).config;
  const history=overview('history');
  assert.equal(history.data.datasets[0].label,'2026');
  assert.equal(history.data.datasets[0].data[1].x,null);
  assert.equal(history.data.datasets[1].data[1].x,2);
  const children=overview('children');
  assert.equal(children.data.datasets[0].data[1].x,null);
  assert.equal(children.data.datasets[1].data[1].x,null);
  assert.equal(children.options.scales.x.min,1);
  assert.equal(children.options.scales.x.max,5);
  assert.equal(children.data.datasets.find(ds=>ds.id==='parent').data[0].x,3.5);
  assert.equal(children.data.datasets.find(ds=>ds.id==='parent').data[1].x,null);
  assert.equal(children.data.datasets.find(ds=>ds.id==='total').ns[0],30);
  // Legendenauswahl bleibt auch beim Entfernen und Wiedereinfügen einer Reihe bestehen.
  children.data.datasets.find(ds=>ds.id==='parent').hidden=true;
  elements['show-total'].checked=false;events.total();
  assert.equal(overview('children').data.datasets.some(ds=>ds.id==='total'),false);
  elements['show-total'].checked=true;events.total();
  assert.equal(overview('children').data.datasets.find(ds=>ds.id==='total').data[0].x,3.8);
  elements['show-parent'].checked=false;events.parent();
  assert.equal(overview('children').data.datasets.some(ds=>ds.id==='parent'),false);
  elements['show-parent'].checked=true;events.parent();
  assert.equal(overview('children').data.datasets.find(ds=>ds.id==='parent').hidden,true);
  elements['report-metric'].value='top2';events.metric();
  await events.png();
  const exported=configurations.at(-1).config;
  assert.equal(downloads.length,1);
  assert.equal(exported.options.scales.x.min,0);
  assert.equal(exported.options.scales.x.max,100);
  assert.equal(exported.data.datasets[0].data[0].x,80);
  assert.equal(exported.data.datasets[1].hidden,true);
  assert.equal(exported.data.datasets.find(ds=>ds.id==='parent').hidden,true);
  assert.equal(exported.data.datasets.find(ds=>ds.id==='total').data[0].x,76);
  assert.equal(exported.options.responsive,false);
  assert.equal(exported.options.plugins.valueLabels.edge,true);
  assert.equal(exported.data.datasets.every(ds=>ds.data.every(point=>Number.isFinite(point.y))),true);
  assert.match(exported.data.labels[0].join(' '),/Vollständiger Wortlaut A/);
  assert.match(exported.data.labels[1].join(' '),/n: – \/ –/);
  console.log('Themenexport: Metrik, fehlende aktuelle Werte, n und Legendenauswahl geprüft.');
})().catch(error=>{console.error(error);process.exitCode=1;});
