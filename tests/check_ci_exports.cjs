// Konfigurations-, Zeichen- und Exportprüfung ohne Browser.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
  const configs=[],events={},names=[];
  const row={type:'scale',wave:'2026',n:10,mean:4,top2:80,minimum:1,maximum:5,
    mean_ci95:[3,5],top2_ci95:[49,94]};
  const complete={...row,wave:'2027',complete_population:true,mean_ci95:null,top2_ci95:null};
  const payload={project:'Test',unit:'Bereich',cards:[{label:'Frage',rows:[row,complete],
    children:[{...row,unit:'Team'},{...complete,unit:'Vollständig'}],comparisons:[{kind:'parent',label:'Amt',rows:[row,complete]}]}]};
  const section={open:false,addEventListener(name,fn){events[name]=fn;}};
  const elements={'chart-data':{textContent:JSON.stringify(payload)},'export-status':{},'chart-0':{closest:()=>section},'children-0':{},
    'report-metric':{value:'mean',addEventListener(name,fn){events.metric=fn;}},
    'show-ci':{checked:false,addEventListener(name,fn){events.ci=fn;}},'ci-note':{hidden:true},'all-charts':{addEventListener(){}}};
  const buttons=['history','children'].map(view=>({dataset:{index:'0',png:'wide',view},addEventListener(n,fn){events[view]=fn;}}));
  class Chart {
    static defaults={font:{}};
    constructor(canvas,config){this.data=config.data;configs.push({canvas,config});}
    isDatasetVisible(i){return !this.data.datasets[i].hidden;}
    update(){}destroy(){}
  }
  const document={fonts:{ready:Promise.resolve()},body:{dataset:{},appendChild(){}},getElementById:id=>elements[id],
    querySelectorAll:selector=>selector==='[data-png]'?buttons:[],createElement:tag=>tag==='canvas'
      ? {toBlob(fn){fn(new Blob(['PNG']));}} : {click(){names.push(this.download);},remove(){}}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/report-charts.js'),'utf8'),{
    document,window:{devicePixelRatio:1},Chart,Intl,Map,Promise,Blob,setTimeout:()=>0,
    URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}}
  });
  assert.equal(configs.length,0);
  elements['show-ci'].checked=true;events.ci();
  elements['show-ci'].checked=false;events.ci();
  assert.equal(configs.length,0);
  section.open=true;events.toggle();
  assert.equal(configs.length,2);
  events.toggle();
  assert.equal(configs.length,2);
  const current=id=>configs.filter(r=>r.canvas===elements[id]).at(-1).config;
  assert.equal(current('chart-0').options.plugins.confidenceIntervals.enabled,false);
  current('chart-0').data.datasets[1].hidden=true;
  elements['show-ci'].checked=true;events.ci();
  assert.equal(elements['ci-note'].hidden,false);
  const history=current('chart-0'),children=current('children-0');
  assert.equal(history.options.plugins.confidenceIntervals.enabled,true);
  assert.equal(history.data.datasets[1].hidden,true);
  assert.equal(history.data.datasets[1].ci95,undefined); // Keine Intervalle für Vergleichslinien.
  assert.equal(children.options.plugins.confidenceIntervals.horizontal,true);
  const tip=history.options.plugins.tooltip.callbacks.label({dataset:history.data.datasets[0],datasetIndex:0,dataIndex:0,parsed:{y:4}});
  assert.match(tip.join(' '),/95%-KI: 3\.00–5\.00/);
  const completeTip=history.options.plugins.tooltip.callbacks.label({dataset:history.data.datasets[0],datasetIndex:0,dataIndex:1,parsed:{y:4}});
  assert.match(completeTip,/4\.00\* · n=10/);
  assert.doesNotMatch(completeTip,/nicht berechenbar|95%-KI/);
  assert.equal(history.data.datasets[0].ci95[1],null);
  assert.equal(children.data.datasets[0].completePopulation[1],true);
  const printed=[];
  history.plugins.find(p=>p.id==='valueLabels').afterDatasetsDraw({
    ctx:{save(){},restore(){},fillText(text){printed.push(text);}},
    data:history.data,config:{type:'line'},options:{plugins:{}},isDatasetVisible:()=>true,
    getDatasetMeta:()=>({data:[{x:20,y:20},{x:40,y:20}]})
  },null,history.options.plugins.valueLabels);
  assert.deepEqual(printed,['4.00','4.00*']);
  const lines=[];let strokes=0;
  const ctx={save(){},restore(){},beginPath(){},rect(){},clip(){},moveTo(x,y){lines.push([x,y]);},lineTo(x,y){lines.push([x,y]);},stroke(){strokes++;}};
  const stub={ctx,chartArea:{left:0,right:100,top:0,bottom:100},data:children.data,
    scales:{x:{getPixelForValue:v=>v*10},y:{getPixelForValue:v=>v*10}},
    isDatasetVisible:()=>true,getDatasetMeta:()=>({data:[{x:40,y:20}]})};
  const plugin=children.plugins.find(p=>p.id==='confidenceIntervals');
  plugin.afterDatasetsDraw(stub,null,children.options.plugins.confidenceIntervals);
  assert.deepEqual(lines.slice(0,2),[[30,20],[50,20]]);
  assert.equal(strokes,1);
  stub.isDatasetVisible=()=>false;plugin.afterDatasetsDraw(stub,null,children.options.plugins.confidenceIntervals);
  assert.equal(strokes,1);
  stub.isDatasetVisible=()=>true;lines.length=0;
  plugin.afterDatasetsDraw(stub,null,history.options.plugins.confidenceIntervals);
  assert.deepEqual(lines.slice(0,2),[[40,30],[40,50]]);
  stub.data={datasets:[{data:[4],ci95:[null]}]};
  plugin.afterDatasetsDraw(stub,null,history.options.plugins.confidenceIntervals);
  assert.equal(strokes,2); // Fehlende Grenzen erzeugen keine künstlichen Fehlerbalken.
  await events.history();assert.match(names.at(-1),/_ci95\.png$/);
  assert.equal(configs.at(-1).config.data.datasets[0].completePopulation[1],true);
  assert.equal(configs.at(-1).config.options.plugins.confidenceIntervals.enabled,true);
  await events.children();assert.equal(configs.at(-1).config.options.plugins.confidenceIntervals.horizontal,true);
  elements['report-metric'].value='top2';events.metric();await events.history();
  assert.equal(configs.at(-1).config.data.datasets[0].ci95[0][0],49);
  assert.match(configs.at(-1).config.options.plugins.subtitle.text.join(' '),/Wilson/);
  elements['show-ci'].checked=false;events.ci();await events.history();
  assert.equal(elements['ci-note'].hidden,true);
  assert.doesNotMatch(names.at(-1),/_ci95\.png$/);
  assert.equal(configs.at(-1).config.options.plugins.confidenceIntervals.enabled,false);
  section.open=false;events.toggle();
  const count=configs.length;
  elements['report-metric'].value='mean';events.metric();
  assert.equal(configs.length,count);
  await events.history();
  assert.equal(configs.length,count+1);
  assert.equal(configs.at(-1).config.data.datasets[1].hidden,true);
  section.open=true;events.toggle();
  assert.equal(current('chart-0').data.datasets[1].hidden,true);
  assert.equal(current('chart-0').data.datasets[0].data[0],4);
  console.log('Konfidenzintervalle: Schalter, Schutz, Zeichenrichtung, Tooltip und Export geprüft.');
})().catch(e=>{console.error(e);process.exitCode=1;});
