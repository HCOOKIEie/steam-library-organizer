/* Two bounded, interactive motion worlds. Original Canvas2D; no library. */
(() => {
  const root=document.documentElement;
  const $=id=>document.getElementById(id);
  let loaded=false, paused=false, frame=0, replayTimer=0, observer=null;
  let context=null, stage=null, art=null, canvas=null, water=null, waterContext=null, waterPixels=null, width=0, height=0, inView=true;
  let last=0, until=0, elapsed=0, theme='', sceneInView=true;
  let hero=null, reveal=null, revealA=null, revealB=null;
  let target=[0,0], position=[0,0], velocity=[0,0], bursts=[];
  const fine=window.matchMedia('(hover: hover) and (pointer: fine)');
  try { paused=localStorage.getItem('steam-organizer-persona-paused')==='true'; } catch (_) {}
  const selected=()=>['p3r','p5r'].includes(root.dataset.appearance);
  const reduced=()=>root.dataset.motion==='reduced';
  const review=()=>Boolean($('preview-panel')?.classList.contains('has-preview'));
  const allowed=()=>selected()&&!paused&&!reduced()&&!document.hidden&&inView&&sceneInView;
  function controls() {
    root.dataset.personaPaused=String(paused);
    $('persona-pause').disabled=reduced();
    $('persona-pause').setAttribute('aria-pressed',String(paused||reduced()));
    $('persona-pause-label').textContent=reduced()?'已减少动效':paused?'继续动效':'暂停动效';
    $('persona-replay').disabled=paused||reduced();
  }
  function stop(reset=false) {
    cancelAnimationFrame(frame); frame=0; root.dataset.personaRunning='false';
    if(reset) {
      clearReveal(); hero?.style.removeProperty('--water-drift');
      target=[0,0]; position=[0,0]; velocity=[0,0]; bursts=[];
      stage.style.removeProperty('--persona-x'); stage.style.removeProperty('--persona-y');
      context?.clearRect(0,0,width,height);
    }
  }
  function resize() {
    if(!context) return;
    const bounds=art.getBoundingClientRect();
    if(!bounds.width||!bounds.height) return;
    if(width!==bounds.width||height!==bounds.height) {
      width=bounds.width; height=bounds.height;
      const dpr=Math.min(window.devicePixelRatio||1,1.4);
      canvas.width=Math.round(width*dpr); canvas.height=Math.round(height*dpr);
      context.setTransform(dpr,0,0,dpr,0,0);
    }
  }
  // Observed reference: John Persona's in-game recording, menu return at ~8s.
  // Two opposite circular windows reveal the new composition; they are not rings.
  function clearReveal() {
    reveal=null;
    hero?.style.removeProperty('clip-path');
    if(hero) delete hero.dataset.revealing;
  }
  function startReveal() {
    if(root.dataset.appearance!=='p3r'||!allowed()||review()||!hero||!revealA||!revealB) return;
    const b=hero.getBoundingClientRect();
    if(!b.width||!b.height) return;
    // The opposite origins share coverage; a full diagonal erases both contours too early.
    reveal={time:performance.now(),radius:Math.hypot(b.width,b.height)*.68};
    for(const [circle,x,y] of [[revealA,.86,.08],[revealB,.08,.94]]) {
      circle.setAttribute('cx',String(b.width*x)); circle.setAttribute('cy',String(b.height*y)); circle.setAttribute('r','0');
    }
    hero.style.clipPath='url(#reload-menu-reveal)'; hero.dataset.revealing='true'; wake(1200);
  }
  function paintReveal(now) {
    if(!reveal) return;
    const age=now-reveal.time;
    const progress=delay=>Math.max(0,Math.min(1,(age-delay)/460));
    // Slight stagger keeps the two circular windows distinct at the start.
    revealA.setAttribute('r',String(reveal.radius*Math.pow(progress(0),.9)));
    revealB.setAttribute('r',String(reveal.radius*Math.pow(progress(55),.9)));
    if(age>=515) clearReveal();
  }
  // Broad water-surface reflections descend into cobalt, not a neon vein grid.
  // Low resolution is intentional: the source has soft, refracted background light.
  function paintWater(t) {
    if(!waterPixels) return;
    const data=waterPixels.data, w=water.width, h=water.height;
    for(let y=0;y<h;y++) for(let x=0;x<w;x++) {
      const u=x/w*6, depth=y/h, v=depth*5;
      const warp=Math.sin(u*1.2+t*.18)*.6+Math.sin(v*1.5-t*.14)*.45;
      const flow=Math.sin(u*2.9+warp+t*.22)*.48+Math.sin(v*6.8+Math.sin(u*1.7-t*.2)*1.8)*.33+Math.cos(u*4.1-v*2.7+t*.13)*.2;
      const patches=Math.pow(Math.max(0,Math.min(1,(flow+.18)*1.1)),2);
      const surface=Math.pow(Math.max(0,1-depth*1.45),1.3);
      const light=surface*(patches*72+Math.sin(u*.6-t*.1)*5);
      const d=Math.pow(depth,.65), i=(y*w+x)*4;
      data[i]=2+light*.12; data[i+1]=181-d*110+light*.85;
      data[i+2]=225-d*28+light*.32; data[i+3]=255;
    }
    waterContext.putImageData(waterPixels,0,0);
  }
  function star(x,y,r,angle) {
    context.beginPath();
    for(let i=0;i<10;i++) {
      const a=angle+i*Math.PI/5, length=i%2?r*.34:r;
      const px=x+Math.cos(a)*length*1.15, py=y+Math.sin(a)*length*.8;
      if(i===0) context.moveTo(px,py); else context.lineTo(px,py);
    }
    context.closePath();
  }
  function paint(now) {
    if(!context||!width||!height||review()) return;
    context.clearRect(0,0,width,height);
    const blue=theme==='p3r';
    if(blue) { paintWater(elapsed/1000); hero.style.setProperty('--water-drift',`${(Math.sin(elapsed/3200)*4).toFixed(2)}px`); }
    bursts=bursts.filter(b=>now-b.time<(blue?900:580));
    for(const b of bursts) {
      const age=now-b.time, p=Math.min(1,age/(blue?900:580));
      const out=1-Math.pow(1-p,3), fade=Math.pow(1-p,1.2);
      if(!blue) {
        context.save();
        context.globalAlpha=fade;
        const r=20+out*100;
        star(b.x,b.y,r,-Math.PI/2+b.angle);
        context.lineWidth=9; context.strokeStyle='#fff9ed'; context.stroke();
        context.fillStyle='#101010'; context.fill();
        star(b.x,b.y,r*.38,-Math.PI/2+b.angle+.12);
        context.fillStyle='#fff9ed'; context.fill();
        // A sharp manga speed cut, instead of scattered generic confetti.
        context.beginPath(); context.moveTo(b.x-r*1.7,b.y+r*.65);
        context.lineTo(b.x-r*.28,b.y+r*.1); context.lineTo(b.x-r*.9,b.y+r*.6);
        context.closePath(); context.fill(); context.restore();
      }
    }
  }
  function tick(now) {
    frame=0;
    if(!allowed()||review()) { stop(true); return; }
    if(last&&now-last<32) { frame=requestAnimationFrame(tick); return; }
    const dt=Math.min(50,last?now-last:16)/1000; last=now; elapsed+=dt*1000;
    for(let i=0;i<2;i++) {
      velocity[i]+=(target[i]-position[i])*110*dt;
      velocity[i]*=Math.exp(-16*dt); position[i]+=velocity[i]*dt;
    }
    stage.style.setProperty('--persona-x',position[0].toFixed(4));
    stage.style.setProperty('--persona-y',position[1].toFixed(4));
    resize(); paint(now); paintReveal(now);
    const settling=position.some((v,i)=>Math.abs(v-target[i])>.001||Math.abs(velocity[i])>.01);
    if((theme==='p3r'&&waterPixels)||now<until||settling||bursts.length) frame=requestAnimationFrame(tick);
    else stop();
  }
  function wake(duration=2200) {
    if(!allowed()||review()) { stop(true); return; }
    theme=root.dataset.appearance; until=performance.now()+duration;
    root.dataset.personaRunning='true'; last=0;
    if(!frame) frame=requestAnimationFrame(tick);
  }
  function burst(x,y) {
    if(!allowed()||review()) return;
    if(root.dataset.appearance==='p3r') { startReveal(); return; }
    bursts.push({x,y,time:performance.now(),angle:bursts.length*.7});
    if(bursts.length>4) bursts.shift(); wake();
  }
  function replay() {
    if(!allowed()) return;
    clearTimeout(replayTimer); stage.classList.remove('persona-replay');
    void stage.offsetWidth; stage.classList.add('persona-replay');
    replayTimer=setTimeout(()=>stage.classList.remove('persona-replay'),840);
    resize(); burst(width*.72,height*.4); wake(8000);
  }
  function sync() {
    const h=hero.getBoundingClientRect(), s=stage.getBoundingClientRect();
    sceneInView=h.width>0&&h.height>0&&h.bottom>s.top&&h.top<s.bottom;
    controls();
    if(selected()&&(paused||reduced())) root.classList.remove('appearance-enter','preview-reveal');
    if(!allowed()||review()) { clearTimeout(replayTimer); stage.classList.remove('persona-replay'); stop(true); }
    else wake(6000);
  }
  function init() {
    if(loaded||!$('persona-canvas')) return; loaded=true;
    canvas=$('persona-canvas'); stage=canvas.closest('.stage'); art=$('persona-art');
    hero=art.closest('.persona-hero'); revealA=$('reload-reveal-a'); revealB=$('reload-reveal-b');
    if(typeof CanvasRenderingContext2D!=='undefined') { try { context=canvas.getContext('2d',{alpha:true}); } catch (_) {} }
    water=document.createElement('canvas'); water.className='persona-water'; water.setAttribute('aria-hidden','true');
    water.width=224; water.height=112; hero.prepend(water);
    if(context) {
      waterContext=water.getContext('2d',{alpha:false});
      if(waterContext?.createImageData) { waterPixels=waterContext.createImageData(water.width,water.height); paintWater(0); }
    }
    $('persona-pause').addEventListener('click',()=>{
      if(reduced()) return; paused=!paused;
      try { localStorage.setItem('steam-organizer-persona-paused',String(paused)); } catch (_) {}
      sync();
    });
    $('persona-replay').addEventListener('click',replay);
    art.addEventListener('pointermove',event=>{
      if(!allowed()||review()||!fine.matches||event.pointerType==='touch') return;
      const b=art.getBoundingClientRect(), x=event.clientX-b.left, y=event.clientY-b.top;
      target=[Math.max(-1,Math.min(1,x/Math.max(b.width,1)*2-1)),Math.max(-1,Math.min(1,y/Math.max(b.height,1)*2-1))];
      wake();
    },{passive:true});
    art.addEventListener('pointerleave',()=>{ target=[0,0]; if(allowed()) wake(1000); });
    art.addEventListener('click',event=>{
      const b=art.getBoundingClientRect(); burst(event.clientX-b.left,event.clientY-b.top);
    });
    art.addEventListener('keydown',event=>{
      if(event.key==='Enter'||event.key===' ') { event.preventDefault(); resize(); burst(width*.5,height*.5); }
    });
    stage.addEventListener('scroll',sync,{passive:true});
    window.addEventListener('organizer-appearance-change',()=>{ stop(true); sync(); if(root.classList.contains('appearance-enter')) startReveal(); });
    window.addEventListener('organizer-motion-change',sync);
    window.addEventListener('organizer-state-change',()=>queueMicrotask(()=>{ if(review()) stop(true); }));
    window.addEventListener('organizer-preview-ready',()=>{ stop(true); });
    document.addEventListener('visibilitychange',sync);
    window.addEventListener('resize',()=>{ clearReveal(); wake(1000); },{passive:true});
    if(typeof IntersectionObserver!=='undefined') {
      observer=new IntersectionObserver(entries=>{ inView=entries[0].isIntersecting; sync(); }); observer.observe(stage);
    }
    window.addEventListener('pagehide',()=>{ clearTimeout(replayTimer); stage.classList.remove('persona-replay'); stop(true); observer?.disconnect(); });
    window.addEventListener('pageshow',()=>{ observer?.observe(stage); sync(); });
    sync();
    if(root.classList.contains('appearance-enter')) startReveal();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init,{once:true}); else init();
})();
