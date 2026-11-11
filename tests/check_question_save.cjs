const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const path=require('node:path');

async function run(renew) {
  const events={},requests=[];
  const token={value:'old-token'};
  const status={textContent:'',classList:{add(){},remove(){}}};
  const form={
    get action(){throw new Error('DOM-clobbered form.action must never be used');},
    getAttribute(){return null;},
    addEventListener(name,fn){events[name]=fn;},
    querySelectorAll(){return [];},
    querySelector(){return token;}
  };
  const document={
    getElementById(id){if(id==='questions-form')return form;if(id==='question-save-status')return status;return {addEventListener(){}};},
    querySelectorAll(){return [];}
  };
  class FormData extends Map {constructor(){super([['csrf','old-token'],['label_0','Erhaltene Änderung']]);}}
  let posts=0;
  const response=(status,body)=>({status,ok:status>=200&&status<300,headers:{get(){return 'application/json';}},json:async()=>body});
  const fetch=async(url,options)=>{
    requests.push({url,token:options.body?.get('csrf'),label:options.body?.get('label_0')});
    if(url==='/session/csrf')return response(200,{csrf:'new-token'});
    assert.equal(url,'http://127.0.0.1:5051/p/1/questions');
    posts++;
    if(renew && posts===1)return response(400,{code:'csrf_expired'});
    return response(200,{message:'Gespeichert',reload:false});
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/questions.js'),'utf8'),{
    document,FormData,fetch,location:{pathname:'/p/1/questions',href:'http://127.0.0.1:5051/p/1/questions'},
    window:{addEventListener(){}},sessionStorage:{getItem(){return null;}},TypeError
  });
  await events.submit({preventDefault(){},submitter:{name:'action',value:'save'}});
  assert.equal(status.textContent,'Gespeichert');
  assert.equal(posts,renew?2:1);
  if(renew){assert.equal(requests.at(-1).token,'new-token');assert.equal(requests.at(-1).label,'Erhaltene Änderung');}
}
(async()=>{await run(false);await run(true);console.log('Speicheradresse und einmalige Sitzungserneuerung geprüft.');})().catch(error=>{console.error(error);process.exitCode=1;});
