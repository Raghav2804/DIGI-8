document.getElementById('menuToggle')?.addEventListener('click',()=>document.getElementById('sidebar').classList.toggle('open'));
document.addEventListener('click',e=>{let s=document.getElementById('sidebar'),b=document.getElementById('menuToggle');if(s?.classList.contains('open')&&!s.contains(e.target)&&!b.contains(e.target))s.classList.remove('open')});
