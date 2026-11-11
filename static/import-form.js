(() => {
  'use strict';
  const format=document.getElementById('data-mode');
  const wave=document.getElementById('wave-mode');
  function update() {
    document.querySelectorAll('[data-format]').forEach(el=>{
      el.hidden=el.dataset.format!==format.value;
    });
    document.querySelectorAll('[data-wave]').forEach(el=>{
      el.hidden=!el.dataset.wave.split(' ').includes(wave.value);
    });
  }
  format.addEventListener('change',update);
  wave.addEventListener('change',update);
  document.getElementById('add-period').addEventListener('click',()=>{
    const body=document.getElementById('period-rows');
    const row=body.firstElementChild.cloneNode(true);
    row.querySelectorAll('input').forEach(input=>input.value='');
    body.appendChild(row);
    row.querySelector('input').focus();
  });
  update();
})();
