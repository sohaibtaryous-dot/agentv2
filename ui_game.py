# -*- coding: utf-8 -*-
"""Mini-jeux affichés pendant les longs traitements (comme l'attente chez Flexport) :
  ⚽ Penalty : on clique dans le but pour tirer, le gardien plonge pour essayer d'arrêter le ballon (5 tirs par série).
  🧠 Quiz   : calculs / équations, culture générale, douane et logistique (4 réponses possibles).
Les jeux tournent côté navigateur : ils continuent pendant que le serveur calcule, puis disparaissent tout seuls quand le résultat est prêt."""

from __future__ import annotations

from contextlib import contextmanager

import streamlit as st
import streamlit.components.v1 as components

HEIGHT = 330

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent;font-family:Inter,system-ui,Segoe UI,sans-serif;color:#E6EBF5;overflow:hidden}
.box{border:1px solid rgba(96,165,250,.35);border-radius:18px;background:linear-gradient(160deg,#0e1730,#0a1020 70%);padding:10px 12px 12px;box-shadow:0 18px 40px rgba(0,0,0,.4)}
.top{display:flex;justify-content:space-between;align-items:center;font-size:13px;margin-bottom:8px;gap:8px;flex-wrap:wrap}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#3B82F6;margin-right:7px;animation:p 1.2s ease-in-out infinite}
@keyframes p{50%{opacity:.25}}
.tabs{display:flex;gap:6px}.tabs button{background:rgba(255,255,255,.06);border:1px solid rgba(147,197,253,.3);color:#E6EBF5;border-radius:999px;padding:5px 12px;font-size:12.5px;cursor:pointer}
.tabs button.on{background:#2563EB;border-color:#60A5FA;color:#fff;font-weight:700}
.st{font-weight:600}.st b{color:#93C5FD}
canvas{display:block;width:100%;height:250px;border-radius:12px;cursor:crosshair;touch-action:manipulation;background:linear-gradient(#10224a,#0b1633 45%,#0d3b2e 45%,#0a2a22)}
.hint{font-size:12px;color:rgba(230,235,245,.65);margin-top:6px;text-align:center;min-height:16px}
#quiz{display:none;height:250px;border-radius:12px;background:rgba(255,255,255,.04);padding:14px 16px;flex-direction:column;justify-content:space-between}
#q{font-size:17px;font-weight:600;line-height:1.35;min-height:46px}
#o{display:grid;grid-template-columns:1fr 1fr;gap:8px}
#o button{background:rgba(255,255,255,.07);border:1px solid rgba(147,197,253,.35);color:#E6EBF5;border-radius:12px;padding:11px 8px;font-size:15px;cursor:pointer}
#o button:hover{border-color:#93C5FD}#o button.ok{background:#15803d;border-color:#4ADE80}#o button.ko{background:#b91c1c;border-color:#f87171}
.tag{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#93C5FD}
</style></head><body><div class="box">
<div class="top"><span><span class="dot"></span>__LABEL__</span>
 <span class="tabs"><button id="tp" class="on">&#9917; Penalty</button><button id="tq">&#129504; Quiz</button></span>
 <span class="st" id="stat"></span></div>
<canvas id="c" width="760" height="250"></canvas>
<div id="quiz"><div><div class="tag" id="tg"></div><div id="q"></div></div><div id="o"></div></div>
<div class="hint" id="h"></div></div>
<script>
(function(){
var $=function(i){return document.getElementById(i)};
var mode='penalty';try{mode=localStorage.getItem('timar_mode')||'penalty'}catch(e){}
function setMode(m){mode=m;try{localStorage.setItem('timar_mode',m)}catch(e){}
  $('tp').className=m==='penalty'?'on':'';$('tq').className=m==='quiz'?'on':'';
  $('c').style.display=m==='penalty'?'block':'none';$('quiz').style.display=m==='quiz'?'flex':'none';
  if(m==='penalty')pen.start();else qz.next();}
$('tp').onclick=function(){setMode('penalty')};$('tq').onclick=function(){setMode('quiz')};

/* ---------------- PENALTY ---------------- */
var c=$('c'),x=c.getContext('2d'),W=c.width,H=c.height;
var GX=250,GY=34,GW=260,GH=100;                       /* cadre du but */
var spot={x:W/2,y:218};
var pen={shots:0,goals:0,busy:false,ball:null,keeper:null,msg:'',t:0,tgt:null,res:null,from:null,kdest:null,done:false};
pen.start=function(){pen.shots=0;pen.goals=0;pen.busy=false;pen.done=false;pen.msg='';pen.reset();pen.stat();$('h').textContent='Cliquez dans le but pour tirer — le gardien essaie d\'arrêter le ballon !';};
pen.reset=function(){pen.ball={x:spot.x,y:spot.y,s:1};pen.keeper={x:GX+GW/2,y:GY+GH-6,rot:0};pen.res=null;pen.busy=false;};
pen.stat=function(){$('stat').innerHTML='Buts <b>'+pen.goals+'</b> / '+pen.shots+' &nbsp; (5 tirs)';};
function zone(px,py){var cx=Math.min(2,Math.max(0,Math.floor((px-GX)/(GW/3)))),cy=py<GY+GH/2?0:1;return {cx:cx,cy:cy};}
function zc(z){return {x:GX+GW/6+z.cx*GW/3,y:GY+GH/4+z.cy*GH/2};}
c.addEventListener('mousedown',shoot);c.addEventListener('touchstart',function(e){e.preventDefault();shoot(e)},{passive:false});
function shoot(e){if(mode!=='penalty')return;
  if(pen.done){pen.start();return;}
  if(pen.busy)return;
  var r=c.getBoundingClientRect(),p=e.touches?e.touches[0]:e,tx=(p.clientX-r.left)*W/r.width,ty=(p.clientY-r.top)*H/r.height;
  if(ty>GY+GH+26)return;                                /* il faut viser vers le but */
  pen.tgt={x:tx,y:ty};pen.from={x:spot.x,y:spot.y};pen.busy=true;pen.t=0;
  var inside=tx>GX&&tx<GX+GW&&ty>GY&&ty<GY+GH;
  var kz={cx:Math.floor(Math.random()*3),cy:Math.random()<.5?0:1};         /* le gardien plonge au hasard */
  pen.kdest=zc(kz);
  var tz=zone(tx,ty),saved=false;
  if(inside){var dxz=Math.abs(tz.cx-kz.cx);saved=(tz.cy===kz.cy&&dxz===0)||(dxz===0&&Math.random()<.35)||(dxz===1&&tz.cy===kz.cy&&Math.random()<.25);}
  pen.res=!inside?'miss':(saved?'save':'goal');
  pen.shots++;}
function pdraw(){
  x.clearRect(0,0,W,H);
  x.fillStyle='rgba(255,255,255,.06)';for(var i=0;i<6;i++){x.fillRect(0,GY+GH+20+i*18,W,8);}
  x.strokeStyle='#F8FAFF';x.lineWidth=4;x.strokeRect(GX,GY,GW,GH);          /* poteaux + barre */
  x.strokeStyle='rgba(255,255,255,.14)';x.lineWidth=1;for(var i=1;i<12;i++){x.beginPath();x.moveTo(GX+i*GW/12,GY);x.lineTo(GX+i*GW/12,GY+GH);x.stroke();}
  for(var j=1;j<5;j++){x.beginPath();x.moveTo(GX,GY+j*GH/5);x.lineTo(GX+GW,GY+j*GH/5);x.stroke();}
  x.fillStyle='rgba(255,255,255,.5)';x.beginPath();x.arc(spot.x,spot.y+14,3,0,7);x.fill();
  /* gardien */
  var k=pen.keeper;x.save();x.translate(k.x,k.y);x.rotate(k.rot);
  x.fillStyle='#F59E0B';x.fillRect(-12,-44,24,38);x.fillStyle='#FCD9A8';x.beginPath();x.arc(0,-52,9,0,7);x.fill();
  x.strokeStyle='#F59E0B';x.lineWidth=6;x.lineCap='round';x.beginPath();x.moveTo(-12,-38);x.lineTo(-28,-24);x.moveTo(12,-38);x.lineTo(28,-24);x.stroke();
  x.fillStyle='#fff';x.beginPath();x.arc(-28,-24,5,0,7);x.arc(28,-24,5,0,7);x.fill();
  x.strokeStyle='#1e3a8a';x.beginPath();x.moveTo(-6,-6);x.lineTo(-9,6);x.moveTo(6,-6);x.lineTo(9,6);x.stroke();x.restore();
  /* ballon */
  var b=pen.ball,r=11*b.s;x.beginPath();x.arc(b.x,b.y,r,0,7);x.fillStyle='#F8FAFF';x.fill();x.lineWidth=1.5;x.strokeStyle='#93C5FD';x.stroke();
  x.fillStyle='#10151f';x.beginPath();x.arc(b.x,b.y,r*.38,0,7);x.fill();
  if(pen.msg){x.font='800 30px system-ui';x.textAlign='center';x.fillStyle=pen.res==='goal'?'#4ADE80':(pen.res==='save'?'#F87171':'#FBBF24');x.fillText(pen.msg,W/2,GY+GH+64);}
}
function pstep(){
  if(pen.busy&&pen.tgt){pen.t+=1/38;var t=Math.min(1,pen.t),e=1-Math.pow(1-t,2);
    pen.ball.x=pen.from.x+(pen.tgt.x-pen.from.x)*e;pen.ball.y=pen.from.y+(pen.tgt.y-pen.from.y)*e;pen.ball.s=1-0.45*e;
    var kt=Math.min(1,pen.t*1.5),ke=1-Math.pow(1-kt,2);var kx=GX+GW/2,ky=GY+GH-6;
    pen.keeper.x=kx+(pen.kdest.x-kx)*ke;pen.keeper.y=ky+(pen.kdest.y+44-ky)*ke*0.6;pen.keeper.rot=(pen.kdest.x-kx)/GW*1.3*ke;
    if(t>=1&&!pen.msg){
      if(pen.res==='save'){pen.msg='ARRÊTÉ !';}else if(pen.res==='goal'){pen.msg='BUUUT !';pen.goals++;}else{pen.msg='Hors cadre';}
      pen.stat();pen.after=60;}
    if(pen.msg&&--pen.after<=0){pen.msg='';pen.tgt=null;
      if(pen.shots>=5){pen.done=true;pen.reset();pen.msg=pen.goals+' / 5 — cliquez pour rejouer';pen.res=pen.goals>=3?'goal':'save';$('h').textContent='Série terminée';}
      else{pen.reset();}}}
}
/* ---------------- QUIZ ---------------- */
var CULT=[
["Culture","Quelle est la capitale du Maroc ?","Rabat",["Casablanca","Tanger","Marrakech"]],
["Culture","Quel détroit sépare l'Espagne du Maroc ?","Gibraltar",["Bosphore","Ormuz","Malacca"]],
["Culture","Combien de joueurs par équipe sur le terrain au football ?","11",["9","10","12"]],
["Culture","Qui a gagné la Coupe du monde de football 2022 ?","Argentine",["France","Brésil","Maroc"]],
["Culture","Quel est le plus grand océan ?","Pacifique",["Atlantique","Indien","Arctique"]],
["Culture","Combien de continents compte-t-on généralement ?","7",["5","6","8"]],
["Culture","Quelle est la planète la plus proche du Soleil ?","Mercure",["Vénus","Mars","Terre"]],
["Culture","Quelle est la monnaie du Maroc ?","Le dirham",["Le dinar","Le franc","La livre"]],
["Culture","Combien de jours compte une année bissextile ?","366",["365","364","367"]],
["Douane","Que signifie DUM ?","Déclaration Unique de Marchandises",["Document Unique de Manutention","Droit Unique de Mer","Dossier Unifié de Marchandises"]],
["Douane","Que signifie « HT » sur une facture ?","Hors taxes",["Haute tension","Hors transport","Hors tarif"]],
["Douane","Le Système Harmonisé (SH) classe les marchandises avec combien de chiffres communs ?","6",["4","8","10"]],
["Logistique","Que signifie CIF (Incoterm) ?","Coût, assurance et fret",["Contrôle et inspection des frets","Chargement immédiat franco","Coût indirect forfaitaire"]],
["Logistique","Que signifie FOB (Incoterm) ?","Free On Board (franco à bord)",["Freight On Board","Fast Order Bill","Free Of Bill"]],
["Logistique","Que signifie CMR ?","Contrat de transport international de marchandises par route",["Contrôle des marchandises routières","Code maritime règlementaire","Certificat de mise en route"]],
["Logistique","Que signifie TIR ?","Transports Internationaux Routiers",["Transit International Rapide","Taxe d'Import Réduite","Titre d'Impôt Routier"]],
["Logistique","Quel document accompagne la marchandise et détaille son contenu colis par colis ?","La packing list",["Le visa","Le manifeste fiscal","Le bordereau bancaire"]]
];
function rnd(a,b){return a+Math.floor(Math.random()*(b-a+1))}
function shuffle(a){for(var i=a.length-1;i>0;i--){var j=Math.floor(Math.random()*(i+1));var t=a[i];a[i]=a[j];a[j]=t}return a}
function mathQ(){var t=rnd(0,4),q,ans;
  if(t===0){var a=rnd(12,48),b=rnd(6,19);q=a+' × '+b+' = ?';ans=a*b;}
  else if(t===1){var xx=rnd(2,15),m=rnd(2,9),k=rnd(1,30);q='Résolvez : '+m+'x + '+k+' = '+(m*xx+k)+'   →   x = ?';ans=xx;}
  else if(t===2){var p=[10,20,25,50][rnd(0,3)],n=rnd(2,40)*20;q=p+' % de '+n+' = ?';ans=n*p/100;}
  else if(t===3){var xx2=rnd(3,20),m2=rnd(2,6),k2=rnd(2,12);q='Résolvez : '+m2+'x − '+k2+' = '+(m2*xx2-k2)+'   →   x = ?';ans=xx2;}
  else{var r=rnd(4,15);q='√'+(r*r)+' = ?';ans=r;}
  var set={};set[ans]=1;var opts=[ans];while(opts.length<4){var d=ans+rnd(-9,9)||ans+11;if(d>=0&&!set[d]){set[d]=1;opts.push(d)}}
  return {tag:'Calcul',q:q,ans:String(ans),opts:shuffle(opts.map(String))};}
var qz={score:0,streak:0,best:0,locked:false};
try{qz.best=+(localStorage.getItem('timar_quiz')||0)}catch(e){}
qz.next=function(){qz.locked=false;var it;
  if(Math.random()<.5){it=mathQ();}else{var e=CULT[rnd(0,CULT.length-1)];it={tag:e[0],q:e[1],ans:e[2],opts:shuffle([e[2]].concat(e[3]))};}
  $('tg').textContent=it.tag;$('q').textContent=it.q;var o=$('o');o.innerHTML='';
  it.opts.forEach(function(v){var b=document.createElement('button');b.textContent=v;b.onclick=function(){qz.pick(b,v,it)};o.appendChild(b)});
  $('stat').innerHTML='Série <b>'+qz.streak+'</b> &nbsp; Record <b>'+qz.best+'</b>';$('h').textContent='Répondez sans vous presser — le fichier arrive !';};
qz.pick=function(b,v,it){if(qz.locked)return;qz.locked=true;
  var ok=v===it.ans;b.className=ok?'ok':'ko';
  if(!ok){var bs=$('o').children;for(var i=0;i<bs.length;i++)if(bs[i].textContent===it.ans)bs[i].className='ok';qz.streak=0;$('h').textContent='Raté — la bonne réponse : '+it.ans;}
  else{qz.streak++;if(qz.streak>qz.best){qz.best=qz.streak;try{localStorage.setItem('timar_quiz',qz.best)}catch(e){}}$('h').textContent='Bravo ! ✔';}
  setTimeout(qz.next,1300);};
/* ---------------- boucle ---------------- */
function loop(){if(mode==='penalty'){pstep();pdraw();}requestAnimationFrame(loop);}
pen.start();setMode(mode);loop();
})();
</script></body></html>"""


@contextmanager
def playing(label: str = "Votre fichier se prépare… jouez en attendant"):
    """with ui_game.playing(): <traitement long>  — affiche le mini-jeu pendant le traitement, le retire ensuite (même en cas d'erreur)."""
    slot = st.empty()
    try:
        with slot.container():
            components.html(PAGE.replace("__LABEL__", label), height=HEIGHT)
        yield
    finally:
        slot.empty()
