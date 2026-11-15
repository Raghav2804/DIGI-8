(()=>{
const key='careerpulse-saved';const read=()=>JSON.parse(localStorage.getItem(key)||'[]');
document.querySelectorAll('.save-job').forEach(button=>{const id=button.dataset.key;button.classList.toggle('saved',read().includes(id));button.addEventListener('click',()=>{const old=read(),next=old.includes(id)?old.filter(x=>x!==id):[...old,id];localStorage.setItem(key,JSON.stringify(next));button.classList.toggle('saved',next.includes(id))})});
document.getElementById('savedToggle')?.addEventListener('click',event=>{const button=event.currentTarget,on=button.classList.toggle('active'),saved=read();document.querySelectorAll('.job-card').forEach(card=>card.hidden=on&&!saved.includes(card.dataset.key));button.innerHTML=on?'<i class="bi bi-bookmark-fill"></i> All jobs':'<i class="bi bi-bookmark"></i> Saved only'});
})();
