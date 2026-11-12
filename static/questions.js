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
      // Buttons namens "action" überdecken form.action im DOM. Attribut explizit lesen.
      const saveUrl=form.getAttribute('action') || location.href;
      const send=()=>fetch(saveUrl,{method:'POST',body:data,credentials:'same-origin',headers:{Accept:'application/json'}});
      const read=async response=>{
        const type=response.headers.get('Content-Type')||'';
        if(!type.includes('application/json'))throw new Error(`Der Server antwortet mit HTTP ${response.status}, aber nicht im erwarteten Format. Ihre Änderungen bleiben im Formular. Bitte diese Meldung und die letzte CMD-Ausgabe weitergeben.`);
        return response.json();
      };
      let response=await send();
      let result=await read(response);
      if(response.status===400 && result.code==='csrf_expired'){
        // Dieser Fehler entsteht vor dem Speichern. Genau ein Wiederholungsversuch ist sicher.
        status.textContent='Erneuere Formularsitzung ohne Seitenwechsel …';
        const tokenResponse=await fetch('/session/csrf',{credentials:'same-origin',headers:{Accept:'application/json'},cache:'no-store'});
        if(!tokenResponse.ok)throw new Error('Formularsitzung konnte nicht erneuert werden. Änderungen bleiben im Formular.');
        const token=await tokenResponse.json();
        if(!token.csrf)throw new Error('Neue Formularsitzung ist ungültig. Änderungen bleiben im Formular.');
        form.querySelector('input[name=csrf]').value=token.csrf;
        data.set('csrf',token.csrf);
        response=await send();
        result=await read(response);
      }
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
    }catch(error){status.textContent=error instanceof TypeError ? 'Die Verbindung zum Server ist fehlgeschlagen. Prüfen Sie, ob das CMD-Fenster noch läuft. Änderungen bleiben im Formular.' : error.message;status.classList.add('save-error');}
    finally{buttons.forEach(b=>b.disabled=false);}
  });
  const saved=sessionStorage.getItem(key);
  if(saved){
    sessionStorage.removeItem(key);
    try{
      const state=JSON.parse(saved);
      document.querySelectorAll('.question-card').forEach(card=>{card.open=state.open.includes(card.dataset.key);});
      requestAnimationFrame(()=>window.scrollTo(0,state.scroll));
      status.textContent='Änderungen gespeichert. Fragenliste aktualisiert.';
    }catch(error){/* Keine gespeicherte Position. */}
  }
})();
