(() => {
  'use strict';
  const form=document.getElementById('questions-form');
  const status=document.getElementById('question-save-status');
  const key='question-position:'+location.pathname;
  let dirty=false;
  form.addEventListener('input',event=>{if(event.target.id==='question-search')return;dirty=true;status.textContent='Ungespeicherte Änderungen.';});
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  document.getElementById('question-search').addEventListener('input',event=>{
    const search=event.target.value.toLocaleLowerCase();
    document.querySelectorAll('.question-card').forEach(card=>{
      card.hidden=!card.textContent.toLocaleLowerCase().includes(search);
    });
  });
  document.querySelectorAll('.question-select').forEach(label=>{
    label.addEventListener('click',event=>event.stopPropagation());
  });
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    const button=event.submitter;
    const data=new FormData(form);
    if(button?.name)data.set(button.name,button.value);
    const buttons=[...form.querySelectorAll('button[type=submit]')];
    buttons.forEach(b=>b.disabled=true);
    status.classList.remove('save-error');
    status.textContent='Speichere Änderungen …';
    try {
      const response=await fetch(form.action||location.href,{method:'POST',body:data,headers:{Accept:'application/json'}});
      const type=response.headers.get('Content-Type')||'';
      if(!type.includes('application/json'))throw new Error('Die Sitzung ist abgelaufen oder der Server ist nicht erreichbar. Änderungen sind noch im Formular.');
      const result=await response.json();
      if(!response.ok)throw new Error(result.error||'Speichern fehlgeschlagen.');
      dirty=false;
      status.textContent=result.message;
      if(result.reload){
        sessionStorage.setItem(key,JSON.stringify({scroll:window.scrollY,open:[...document.querySelectorAll('.question-card[open]')].map(c=>c.dataset.key)}));
        location.reload();
      } else {
        document.querySelectorAll('.question-card').forEach(card=>{
          card.querySelector('.question-title').textContent=card.querySelector('input[name^=label_]').value;
        });
      }
    }catch(error){status.textContent=error.message;status.classList.add('save-error');}
    finally{buttons.forEach(b=>b.disabled=false);}
  });
  const saved=sessionStorage.getItem(key);
  if(saved){
    sessionStorage.removeItem(key);
    try{
      const state=JSON.parse(saved);
      document.querySelectorAll('.question-card').forEach(card=>{card.open=state.open.includes(card.dataset.key);});
      requestAnimationFrame(()=>window.scrollTo(0,state.scroll));
      status.textContent='Verknüpfung gespeichert. Fragenliste aktualisiert.';
    }catch(error){/* Keine gespeicherte Position. */}
  }
})();
