(() => {
  'use strict';
  const byId=id=>document.getElementById(id);
  const wave=byId('segment-wave'), source=byId('mapping-source');
  const dimension=byId('alias-dimension'), original=byId('alias-source'), target=byId('alias-target');
  const mappingDimension=byId('mapping-dimension');
  const rules=JSON.parse(byId('mapping-rules').textContent);
  const dimensionValue=()=>dimension.value==='__custom__'?byId('alias-custom').value.trim():dimension.value;
  function customFields(){
    for(const prefix of ['mapping','alias']){
      const custom=byId(prefix+'-dimension').value==='__custom__';
      byId(prefix+'-custom-wrap').hidden=!custom;
      byId(prefix+'-custom').required=custom;
    }
  }
  function chooseSavedSource(){
    const dim=mappingDimension.value==='__custom__'?byId('mapping-custom').value.trim():mappingDimension.value;
    const match=rules.find(r=>r.dimension===dim && r.wave===wave.value)
      ||rules.find(r=>r.dimension===dim && r.wave==='*');
    source.value=match?match.source:'';
  }
  let data=null, requestNumber=0, timer;
  function cell(row,value){const td=document.createElement('td');td.textContent=value;row.appendChild(td);return td;}
  function messageRow(body,text,columns){body.replaceChildren();const tr=document.createElement('tr');cell(tr,text).colSpan=columns;body.appendChild(tr);}
  function renderColumns(){
    if(!data)return;
    const body=byId('candidate-columns');body.replaceChildren();
    const search=byId('column-search').value.toLocaleLowerCase();
    const all=byId('all-columns').checked;
    const typical=/Amt|Bereich|Abteilung|Team|HS[1-6]|Hierarchiestufe|RAV|OE |OE_|Alters|Dienst|Geschlecht|Kader|HRV/i;
    for(const col of data.columns){
      if(search && !(col.name+' '+col.examples.join(' ')).toLocaleLowerCase().includes(search))continue;
      if(!search && !all && !typical.test(col.name) && col.name!==source.value)continue;
      const row=document.createElement('tr');
      cell(row,col.name);cell(row,`${col.filled} / ${data.total}`);cell(row,col.distinct);cell(row,col.examples.join(' · '));
      const button=document.createElement('button');button.type='button';button.className='secondary small';button.textContent='Diese Spalte';
      button.addEventListener('click',()=>{source.value=col.name;refresh();byId('source-preview').scrollIntoView({block:'nearest',behavior:'smooth'});});
      cell(row,'').appendChild(button);body.appendChild(row);
    }
    if(!body.children.length)messageRow(body,'Keine passenden befüllten Spalten. Suche anpassen oder alle Datenfelder anzeigen.',5);
  }
  function render(){
    renderColumns();
    byId('source-preview').hidden=!source.value;
    byId('source-summary').textContent=`${data.total} Teilnahmen · ${data.filled} mit Wert · ${data.empty} ohne Wert · ${data.conflicts} mit widersprüchlichen Werten.`;
    const values=byId('source-values');values.replaceChildren();
    data.values.forEach(value=>{const row=document.createElement('tr');cell(row,value.value);cell(row,value.n);values.appendChild(row);});
    if(!data.values.length)messageRow(values,'Diese Spalte ist in der gewählten Erhebung nicht befüllt.',2);
    const selected=original.value;
    original.replaceChildren(new Option('Bitte auswählen',''));
    const unique=new Map();
    data.effective.forEach(row=>unique.set(row.source,(unique.get(row.source)||0)+row.n));
    unique.forEach((n,value)=>original.add(new Option(`${value} (${n} Teilnahmen)`,value)));
    if(unique.has(selected))original.value=selected;
    const names=new Set(data.effective.flatMap(row=>[row.source,row.current]));
    byId('existing-values').replaceChildren(...[...names].map(value=>new Option(value,value)));
    byId('alias-summary').textContent=dimensionValue()
      ? `${data.mapped} von ${data.total} Teilnahmen dem Merkmal zugeordnet · ${data.unmapped} ohne Zuordnung · ${data.mapping_conflicts} mit widersprüchlichen Werten.`
      : 'Bitte ein Merkmal wählen.';
    const aliases=byId('alias-preview');aliases.replaceChildren();
    data.effective.forEach(value=>{const row=document.createElement('tr');cell(row,value.source);cell(row,value.current);cell(row,value.after);cell(row,value.n);if(value.current!==value.after)row.className='preview-change';aliases.appendChild(row);});
    if(!data.effective.length)messageRow(aliases,'Noch keine Werte für dieses Merkmal. Zuerst oben eine passende Spalte auswählen und die Zuordnung speichern.',4);
    byId('resulting-preview').hidden=!data.effective.length;
    const resulting=byId('resulting-values');resulting.replaceChildren();
    data.resulting.forEach(value=>{const row=document.createElement('tr');cell(row,value.value);cell(row,value.n);resulting.appendChild(row);});
  }
  async function refresh(){
    const mine=++requestNumber;
    const url=new URL(location.href);url.pathname=url.pathname.replace(/\/$/,'')+'/preview';
    url.search=new URLSearchParams({wave:wave.value,source:source.value,dimension:dimensionValue(),original:original.value,target:target.value});
    document.querySelectorAll('input[type=hidden][name=wave]').forEach(input=>input.value=wave.value);
    byId('preview-error').hidden=true;
    try{
      const response=await fetch(url,{headers:{Accept:'application/json'},credentials:'same-origin',cache:'no-store'});
      const result=await response.json();
      if(mine!==requestNumber)return;
      if(!response.ok)throw new Error(result.error||'Vorschau konnte nicht geladen werden.');
      data=result;render();
    }catch(error){if(mine!==requestNumber)return;byId('preview-error').textContent=error.message;byId('preview-error').hidden=false;}
  }
  const later=()=>{clearTimeout(timer);timer=setTimeout(refresh,300);};
  byId('scope-form').addEventListener('submit',event=>{event.preventDefault();refresh();});
  wave.addEventListener('change',()=>{original.value='';target.value='';chooseSavedSource();refresh();});
  source.addEventListener('change',refresh);
  mappingDimension.addEventListener('change',()=>{
    dimension.value=mappingDimension.value;
    byId('alias-custom').value=byId('mapping-custom').value;
    original.value='';target.value='';customFields();chooseSavedSource();refresh();
  });
  byId('mapping-custom').addEventListener('input',()=>{
    dimension.value='__custom__';byId('alias-custom').value=byId('mapping-custom').value;
    customFields();later();
  });
  dimension.addEventListener('change',()=>{original.value='';target.value='';customFields();refresh();});
  byId('alias-custom').addEventListener('input',later);
  original.addEventListener('change',refresh);target.addEventListener('input',later);
  byId('column-search').addEventListener('input',renderColumns);byId('all-columns').addEventListener('change',renderColumns);
  customFields();
  if(!source.value)chooseSavedSource();
  refresh();
})();
