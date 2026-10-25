/* 光域 spatial studies. Original geometry and shaders; no external runtime assets. */
(() => {
  const root = document.documentElement;
  const $ = id => document.getElementById(id);
  const SCENES = ['prism', 'drift', 'echo'];
  const read = key => { try { return localStorage.getItem(key); } catch (_) { return null; } };
  const write = (key, value) => { try { localStorage.setItem(key, value); } catch (_) {} };
  let scene = SCENES.includes(read('steam-organizer-space-scene')) ? read('steam-organizer-space-scene') : 'prism';
  let paused = read('steam-organizer-particles-paused') === 'true';
  let renderer = null, initialized = false, syncQueued = false, seed = 17, sceneAnimation = null;
  const forcedColors=window.matchMedia('(forced-colors: active)');
  const quiet = () => paused || root.dataset.motion === 'reduced';
  const visible = () => root.dataset.appearance === 'vault' && root.dataset.vaultView !== 'review' && !document.hidden && !forcedColors.matches;
  function cancelFade(){sceneAnimation?.cancel();sceneAnimation=null;}
  const setText = (id, value) => { if ($(id).textContent !== value) $(id).textContent = value; };
  const rand = n => { const v = Math.sin(n * 127.17 + 31.71) * 43758.5453; return v - Math.floor(v); };
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  // Matrices use column-major storage, matching GLSL. The camera belongs to us.
  function multiply(a, b) {
    const result = new Float32Array(16);
    for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) {
      for (let k = 0; k < 4; k++) result[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k];
    }
    return result;
  }
  function camera(width, height, px = 0, py = 0) {
    const eye = [7.8 + px * .9, 12.5 + py * .7, 17.5], target = [0, -.6, 0];
    const unit = v => { const d = Math.hypot(...v); return v.map(x => x / d); };
    const cross = (a,b) => [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
    const dot = (a,b) => a.reduce((s,v,i) => s+v*b[i],0);
    const z = unit(eye.map((v,i)=>v-target[i])), x = unit(cross([0,1,0],z)), y = cross(z,x);
    const view = new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,eye),-dot(y,eye),-dot(z,eye),1]);
    const f = 1 / Math.tan(.43), aspect = width / Math.max(1,height), near = .1, far = 90;
    const projection = new Float32Array([f/aspect,0,0,0,0,f,0,0,0,0,(far+near)/(near-far),-1,0,0,2*far*near/(near-far),0]);
    return multiply(projection,view);
  }
  function project(point, matrix, width, height) {
    const p = [...point,1], q = [0,0,0,0];
    for (let r=0;r<4;r++) for(let c=0;c<4;c++) q[r]+=matrix[c*4+r]*p[c];
    return [(q[0]/q[3]*.5+.5)*width,(-q[1]/q[3]*.5+.5)*height,q[2]/q[3]];
  }
  function heightAt(x,z,time,variation) {
    return Math.sin(x*.43+z*.27+time*.45+variation*.18)*1.1 + Math.cos(z*.62-x*.15-time*.3)*.65;
  }
  function stream(t, lane, spread, time, variation) {
    const angle=t*7.4+lane*2.1+variation*.13;
    return [(t-.5)*29,Math.sin(angle)*5.6+Math.cos(t*10+lane)*spread,Math.cos(angle*.86)*6.2+(lane-1)*3+Math.sin(t*13+lane)*spread];
  }
  function membrane(x,z,time,variation) {
    const r = Math.hypot(x*.8,z);
    return Math.sin(r*.76-time*.7+variation*.14)*1.8*Math.exp(-r*.042)+Math.sin(x*.3-z*.24)*.7;
  }

  function buildGeometry() {
    const mesh=[], lines=[], particles=[];
    // Separate triangular plates, including their thickness and flat side faces.
    const vertex=(point,center,normal,bary,tag)=>mesh.push(...point,...center,...normal,...bary,tag);
    const triangle=(points,center,normal,tag)=>points.forEach((p,i)=>vertex(p,center,normal,[Number(i===0),Number(i===1),Number(i===2)],tag));
    for(let row=-11;row<12;row++) for(let col=-13;col<14;col++) {
      const a=[col*1.26,row*1.1], b=[(col+1)*1.26,row*1.1], c=[col*1.26+.63,(row+1)*1.1];
      for (const corners of [[a,b,c],[b,[c[0]+1.26,c[1]],c]]) {
        const center=[corners.reduce((s,p)=>s+p[0],0)/3,corners.reduce((s,p)=>s+p[1],0)/3];
        const local=corners.map(p=>[(p[0]-center[0])*.94, .22, (p[1]-center[1])*.94]);
        const id=rand(col*7+row*13+corners[0][0]);
        triangle([local[0],local[2],local[1]],center,[0,1,0],id);
        for(let i=0;i<3;i++) {
          const p=local[i],q=local[(i+1)%3], pb=[p[0],0,p[2]],qb=[q[0],0,q[2]];
          const n=[q[2]-p[2],0,p[0]-q[0]], d=Math.hypot(...n); n[0]/=d;n[2]/=d;
          triangle([p,q,pb],center,n,id);triangle([q,qb,pb],center,n,id);
        }
      }
    }
    for(let i=0;i<12000;i++) particles.push(rand(i*3+.1),Math.floor(rand(i*3+1.7)*3),rand(i*3+2.9),rand(i+80));
    // A connected resonant membrane, deliberately unlike disconnected plates.
    const segment=(x,z,u,v)=>lines.push(x,z,u,v);
    for(let z=-12;z<12;z+=.38) for(let x=-15;x<15;x+=.38) {
      segment(x,z,x+.38,z);segment(x,z,x,z+.38);
    }
    return {mesh:new Float32Array(mesh),particles:new Float32Array(particles),lines:new Float32Array(lines)};
  }

  const VERTEX = `#version 300 es
  precision highp float;
  in vec3 aPosition; in vec2 aCenter; in vec3 aNormal; in vec3 aBary; in float aTag;
  uniform mat4 uMatrix; uniform float uTime,uSeed,uScene,uAspect,uPointScale,uHover;
  uniform vec2 uPointer; uniform vec3 uPulses[3];
  out vec3 vNormal,vBary,vWorld; out float vTag,vEnergy,vDepth;
  float terrain(vec2 p) {return sin(p.x*.43+p.y*.27+uTime*.45+uSeed*.18)*1.1+cos(p.y*.62-p.x*.15-uTime*.3)*.65;}
  void main() {
    vec3 p; vec3 normal=aNormal;
    if(uScene<.5) {p=vec3(aCenter.x+aPosition.x,terrain(aCenter)+aPosition.y,aCenter.y+aPosition.z);}
    else if(uScene<1.5) {
      float t=fract(aPosition.x+uTime*.024),lane=aPosition.y,spread=aPosition.z*2.8;
      float angle=t*7.4+lane*2.1+uSeed*.13;
      p=vec3((t-.5)*29.,sin(angle)*5.6+cos(t*10.+lane)*spread,cos(angle*.86)*6.2+(lane-1.)*3.+sin(t*13.+lane)*spread);
      normal=normalize(vec3(sin(angle),.8,cos(angle)));
    } else {
      float r=length(vec2(aPosition.x*.8,aPosition.z));
      p=vec3(aPosition.x,sin(r*.76-uTime*.7+uSeed*.14)*1.8*exp(-r*.042)+sin(aPosition.x*.3-aPosition.z*.24)*.7,aPosition.z);
      normal=vec3(0.,1.,0.);
    }
    vec4 anchor=uMatrix*vec4(p,1.); vec2 uv=anchor.xy/anchor.w;
    float distanceToPointer=length((uv-uPointer)*vec2(uAspect,1.));
    float energy=exp(-distanceToPointer*distanceToPointer*14.)*uHover;
    p.y+=energy*1.25;
    for(int i=0;i<3;i++) {
      float age=uPulses[i].z;
      if(age>=0. && age<2.4) {
        float d=length((uv-uPulses[i].xy)*vec2(uAspect,1.));
        float wave=exp(-pow((d-age*.62)/.14,2.))*pow(1.-age/2.4,2.);
        p.y+=wave*1.7; energy+=wave*.7;
      }
    }
    gl_Position=uMatrix*vec4(p,1.);
    gl_PointSize=(2.2+aTag*3.4)*uPointScale*clamp(26./gl_Position.w,.6,1.8);
    vNormal=normal;vBary=aBary;vWorld=p;vTag=aTag;vEnergy=energy;
    vDepth=clamp((gl_Position.w-12.)/28.,0.,1.);
  }`;
  const FRAGMENT = `#version 300 es
  precision highp float;
  in vec3 vNormal,vBary,vWorld; in float vTag,vEnergy,vDepth;
  uniform float uScene,uLight; uniform vec2 uResolution; uniform vec4 uQuietBox;
  out vec4 color;
  void main() {
    vec3 mineral=vec3(.45,.72,.71), pearl=vec3(.77,.85,.83), copper=vec3(.69,.47,.29);
    float alpha=1.; vec3 rgb;
    if(uScene<.5) {
      float facing=max(0.,dot(normalize(vNormal),normalize(vec3(-.4,.9,.2))));
      float edge=min(min(vBary.x,vBary.y),vBary.z);
      float seam=1.-smoothstep(0.,fwidth(edge)*1.15,edge);
      float etch=1.-smoothstep(.05,.15,length(fract(vWorld.xz*10.)-.5));
      float grain=fract(sin(dot(floor(vWorld.xz*95.),vec2(93.7,41.3)))*13271.9);
      vec3 material=mix(vec3(.075,.105,.13),vec3(.30,.40,.41),facing);
      rgb=material*(.70+vTag*.38)+grain*.012;
      rgb+=mix(copper,mineral,vTag)*pow(.5+.5*sin(vWorld.x*.4+vWorld.z*.25),6.)*.15;
      rgb+=mix(mineral,copper,vTag)*seam*.24;
      rgb+=pearl*etch*.19*step(.8,vNormal.y);
      rgb+=mineral*vEnergy*.22;
      if(uLight>.5) rgb=mix(vec3(.69,.76,.77),vec3(.91,.94,.93),facing)+seam*vec3(-.14,-.12,-.08);
    } else if(uScene<1.5) {
      vec2 q=abs(gl_PointCoord-.5);
      if(q.x+q.y>.48) discard;
      float center=1.-smoothstep(.02,.45,q.x+q.y);
      rgb=mix(mineral,copper,step(.77,vTag))*(.6+center*.65);
      alpha=(.45+vTag*.45)*(1.-vDepth*.25);
      if(uLight>.5) rgb*=.48;
      rgb+=vEnergy*.3;
    } else {
      float ink=.75+.16*sin(vWorld.x*.23+vWorld.z*.18);
      rgb=mix(mineral,copper,smoothstep(-3.,8.,vWorld.z));
      rgb=mix(rgb,pearl,pow(max(0.,sin(vWorld.y*2.)),8.)*.45);
      alpha=ink*(1.-vDepth*.3)+vEnergy*.4;
      if(uLight>.5) rgb*=.52;
    }
    vec2 pixel=vec2(gl_FragCoord.x,uResolution.y-gl_FragCoord.y);
    vec2 outside=max(max(uQuietBox.xy-pixel,pixel-uQuietBox.zw),vec2(0.));
    float clearText=mix(uScene<.5?.42:.82,1.,smoothstep(0.,170.,length(outside)));
    alpha*=clearText;
    rgb*=1.-vDepth*.36;
    color=vec4(rgb,alpha);
  }`;

  function createGPU(canvas) {
    if(typeof WebGL2RenderingContext==='undefined') return null;
    const gl=canvas.getContext('webgl2',{alpha:true,antialias:true,premultipliedAlpha:false,preserveDrawingBuffer:true,powerPreference:'low-power'});
    if(!gl) return null;
    const shaders=[],buffers=[],vaos=[];
    const shader=(type,source)=>{
      const s=gl.createShader(type); shaders.push(s);gl.shaderSource(s,source);gl.compileShader(s);
      if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    };
    const program=gl.createProgram();
    try {
      gl.attachShader(program,shader(gl.VERTEX_SHADER,VERTEX));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,FRAGMENT));gl.linkProgram(program);
      if(!gl.getProgramParameter(program,gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
      gl.useProgram(program);
      const geometry=buildGeometry();
      const attributes=['aPosition','aCenter','aNormal','aBary','aTag'].map(name=>gl.getAttribLocation(program,name));
      const build=(source,kind)=>{
        const vao=gl.createVertexArray();vaos.push(vao);gl.bindVertexArray(vao);
        const buffer=gl.createBuffer();buffers.push(buffer);gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
        let data;
        if(kind===0) data=source;
        else {
          const vertices=[];
          if(kind===1) for(let i=0;i<source.length;i+=4) vertices.push(source[i],source[i+1],source[i+2],0,0,0,1,0,1,0,0,source[i+3]);
          else for(let i=0;i<source.length;i+=2) vertices.push(source[i],0,source[i+1],0,0,0,1,0,1,0,0,.5);
          data=new Float32Array(vertices);
        }
        gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);
        let offset=0;
        [3,2,3,3,1].forEach((size,i)=>{const loc=attributes[i];if(loc>=0){gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,size,gl.FLOAT,false,48,offset*4);}offset+=size;});
        return {vao,count:data.length/12,mode:kind===0?gl.TRIANGLES:kind===1?gl.POINTS:gl.LINES};
      };
      const objects=[build(geometry.mesh,0),build(geometry.particles,1),build(geometry.lines,2)];
      const names=['uMatrix','uTime','uSeed','uScene','uAspect','uPointScale','uHover','uPointer','uPulses[0]','uLight','uResolution','uQuietBox'];
      const uniforms=Object.fromEntries(names.map(name=>[name,gl.getUniformLocation(program,name)]));
      gl.enable(gl.DEPTH_TEST);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
      gl.clearColor(0,0,0,0);
      return {kind:'webgl',resize(w,h){gl.viewport(0,0,w,h);},draw(state){
        gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(program);
        gl.uniformMatrix4fv(uniforms.uMatrix,false,state.matrix);
        gl.uniform1f(uniforms.uTime,state.time);gl.uniform1f(uniforms.uSeed,state.seed);
        gl.uniform1f(uniforms.uScene,SCENES.indexOf(scene));gl.uniform1f(uniforms.uAspect,state.width/state.height);
        gl.uniform1f(uniforms.uPointScale,state.dpr);gl.uniform1f(uniforms.uHover,state.hover);
        gl.uniform2f(uniforms.uPointer,state.pointer[0],state.pointer[1]);
        const pulses=new Float32Array(9).fill(-10);
        state.pulses.forEach((p,i)=>{pulses[i*3]=p.x;pulses[i*3+1]=p.y;pulses[i*3+2]=(state.now-p.time)/1000;});
        gl.uniform3fv(uniforms['uPulses[0]'],pulses);
        gl.uniform1f(uniforms.uLight,state.light?1:0);gl.uniform2f(uniforms.uResolution,canvas.width,canvas.height);
        gl.uniform4fv(uniforms.uQuietBox,new Float32Array(state.quietBox.map(v=>v*state.dpr)));
        const object=objects[SCENES.indexOf(scene)];gl.bindVertexArray(object.vao);gl.drawArrays(object.mode,0,object.count);
      },dispose(){buffers.forEach(b=>gl.deleteBuffer(b));vaos.forEach(v=>gl.deleteVertexArray(v));shaders.forEach(s=>gl.deleteShader(s));gl.deleteProgram(program);}};
    } catch(error) {
      buffers.forEach(b=>gl.deleteBuffer(b));vaos.forEach(v=>gl.deleteVertexArray(v));shaders.forEach(s=>gl.deleteShader(s));gl.deleteProgram(program);
      console.warn('Lightfield GPU unavailable; using the local fallback.',error.message);
      return null;
    }
  }

  function sampleScene(width,height,time=0,variation=seed,pointer=null,pulses=[],now=0,hover=0) {
    const matrix=camera(width,height), items=[];
    const deform=p=>{
      const screen=project(p,matrix,width,height);
      const uv=[screen[0]/width*2-1,1-screen[1]/height*2];
      let energy=0;
      if(pointer) {const d=Math.hypot((uv[0]-pointer[0])*width/height,uv[1]-pointer[1]);energy=Math.exp(-d*d*14)*hover;}
      for(const pulse of pulses) {
        const age=(now-pulse.time)/1000,d=Math.hypot((uv[0]-pulse.x)*width/height,uv[1]-pulse.y);
        energy+=Math.exp(-Math.pow((d-age*.62)/.14,2))*Math.pow(Math.max(0,1-age/2.4),2)*1.36;
      }
      return project([p[0],p[1]+energy*1.25,p[2]],matrix,width,height);
    };
    if(scene==='prism') {
      for(let row=-10;row<11;row++) for(let col=-12;col<13;col++) {
        const a=[col*1.26,row*1.1],b=[(col+1)*1.26,row*1.1],c=[col*1.26+.63,(row+1)*1.1];
        for(const corners of [[a,b,c],[b,[c[0]+1.26,c[1]],c]]) {
          const cx=corners.reduce((s,p)=>s+p[0],0)/3,cz=corners.reduce((s,p)=>s+p[1],0)/3;
          const h=heightAt(cx,cz,time,variation), tag=rand(cx*7+cz*13);
          const points=corners.map(p=>deform([cx+(p[0]-cx)*.94,h+.22,cz+(p[1]-cz)*.94]));
          items.push({points,tag,depth:points.reduce((s,p)=>s+p[2],0)/3,type:'face'});
        }
      }
    } else if(scene==='drift') {
      for(let i=0;i<1800;i++) {
        const p=stream((rand(i*3+.1)+time*.024)%1,Math.floor(rand(i*3+1.7)*3),rand(i*3+2.9)*2.8,time,variation);
        const point=deform(p);items.push({points:[point],tag:rand(i+80),depth:point[2],type:'star'});
      }
    } else {
      for(let row=-11;row<12;row++) {
        const points=[];
        for(let col=-32;col<=32;col++){const x=col*.46,z=row*.62;points.push(deform([x,membrane(x,z,time,variation),z]));}
        items.push({points,tag:rand(row),depth:points[0][2],type:'line'});
      }
      for(let col=-28;col<=28;col++) {
        const points=[];
        for(let row=-20;row<=20;row++){const x=col*.46,z=row*.35;points.push(deform([x,membrane(x,z,time,variation),z]));}
        items.push({points,tag:rand(col),depth:points[0][2],type:'line'});
      }
    }
    return items.sort((a,b)=>b.depth-a.depth);
  }
  function palette(tag,light,type) {
    if(type==='face') {const v=light?Math.round(185+tag*38):Math.round(30+tag*28);return `rgb(${v},${v+Math.round(light?8:13)},${v+Math.round(light?7:17)})`;}
    if(light) return tag>.77?'#8e684a':'#427b80';
    return tag>.77?'#bba181':tag>.4?'#91b9b8':'#647c8c';
  }
  function fallback(width=1200,height=760) {
    const light=root.dataset.theme==='light';
    const paths=sampleScene(width,height).map(item=>{
      const d=item.points.map((p,i)=>`${i?'L':'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
      if(item.type==='star') {const p=item.points[0];return `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${(1+item.tag).toFixed(1)}" fill="${palette(item.tag,light,item.type)}" opacity=".55"/>`;}
      return `<path d="${d}${item.type==='face'?'Z':''}" fill="${item.type==='face'?palette(item.tag,light,item.type):'none'}" stroke="${light?'#809c9c':'#4a686e'}" stroke-width=".6" opacity="${item.type==='face'?'.88':'.6'}"/>`;
    }).join('');
    $('vault-art-fallback').innerHTML=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid slice">${paths}</svg>`;
  }
  function createCanvas(canvas) {
    if(typeof CanvasRenderingContext2D==='undefined') return null;
    const ctx=canvas.getContext('2d',{alpha:true});if(!ctx)return null;
    return {kind:'canvas',resize(){},draw(state){
      ctx.setTransform(state.dpr,0,0,state.dpr,0,0);ctx.clearRect(0,0,state.width,state.height);
      for(const item of sampleScene(state.width,state.height,state.time,state.seed,state.pointer,state.pulses,state.now,state.hover)) {
        ctx.beginPath();item.points.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));
        if(item.type==='star') {const p=item.points[0],r=1+item.tag;ctx.moveTo(p[0],p[1]-r);ctx.lineTo(p[0]+r,p[1]);ctx.lineTo(p[0],p[1]+r);ctx.lineTo(p[0]-r,p[1]);ctx.closePath();ctx.fillStyle=palette(item.tag,state.light,item.type);ctx.fill();}
        else if(item.type==='face') {ctx.closePath();ctx.fillStyle=palette(item.tag,state.light,item.type);ctx.fill();ctx.strokeStyle=state.light?'#b4c4c4':'#3a5159';ctx.lineWidth=.65;ctx.stroke();}
        else {ctx.strokeStyle=palette(item.tag,state.light,item.type);ctx.lineWidth=.6;ctx.stroke();}
      }
    },dispose(){}};
  }

  function controls() {
    const reduced=root.dataset.motion==='reduced';
    const staticOnly=$('vault-art').dataset.renderer==='fallback'||forcedColors.matches;
    root.dataset.vaultScene=scene;
    document.querySelectorAll('button[data-vault-scene]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.vaultScene===scene)));
    $('vault-pause').disabled=reduced||staticOnly;$('vault-pause').setAttribute('aria-pressed',String(quiet()||staticOnly));
    $('vault-pause').querySelector('svg path').setAttribute('d',quiet()||staticOnly?'m8 5 11 7-11 7Z':'M8 5v14M16 5v14');
    setText('vault-pause-label',reduced?'已减少动效':staticOnly?'静态背景':paused?'继续动态':'暂停动态');
    setText('vault-particle-help',reduced||staticOnly?'静态空间':paused?'动态已暂停':'移动探索 · 点击唤醒');
  }
  function showView(next,focus=false) {
    const review=next==='review'&&!$('vault-review-btn').disabled;
    if(review)cancelFade();
    root.dataset.vaultView=review?'review':'collection';
    $('vault-collection-btn').setAttribute('aria-pressed',String(!review));$('vault-review-btn').setAttribute('aria-pressed',String(review));
    setText('vault-view-title',review?'分类预览':'游戏库');setText('vault-view-copy','');
    renderer?.wake();if(focus&&review)$('preview-search').focus({preventScroll:true});
  }
  function sync() {
    syncQueued=false;const generated=$('preview-badge').textContent!=='尚未生成';
    $('vault-review-btn').disabled=!generated;
    const count=document.querySelectorAll('#groups .group').length;setText('vault-plan-count',count?String(count):'');
    if(!generated&&root.dataset.vaultView==='review')showView('collection');
  }
  function queueSync(){if(!syncQueued){syncQueued=true;queueMicrotask(sync);}}

  function createSpace() {
    let canvas=$('vault-canvas'),engine=createGPU(canvas);
    if(!engine) {
      // A canvas that acquired a GPU context cannot acquire a 2D context.
      const replacement=canvas.cloneNode(false);canvas.replaceWith(replacement);canvas=replacement;
      engine=createCanvas(canvas);
    }
    if(!engine){$('vault-art').dataset.renderer='fallback';return null;}
    $('vault-art').dataset.renderer=engine.kind;
    let width=0,height=0,dpr=1,frame=0,lastTime=null,lastPaint=-Infinity,phase=0,variation=seed,disposed=false,contextLost=false;
    let activeUntil=performance.now()+9000,pointer=[0,0],target=[0,0],hover=0,pointing=false,pulses=[];
    const operating='button,input,label,a,summary,select,[role="tab"],[role="dialog"]';
    const stage=document.querySelector('.stage'),surface=document.querySelector('.vault-exhibit');
    function resize() {
      const w=window.innerWidth||document.documentElement.clientWidth||1200,h=window.innerHeight||document.documentElement.clientHeight||760;
      if(w===width&&h===height)return;
      width=w;height=h;dpr=Math.min(window.devicePixelRatio||1,1.5,Math.sqrt(2000000/(width*height)));
      canvas.width=Math.floor(width*dpr);canvas.height=Math.floor(height*dpr);
      engine.resize(canvas.width,canvas.height);fallback(width,height);
    }
    function render(now) {
      frame=0;if(disposed||contextLost||!visible())return;resize();
      const interval=engine.kind==='webgl'&&now>=activeUntil?32:15;
      if(!quiet()&&now-lastPaint<interval){frame=requestAnimationFrame(render);return;}
      const dt=lastTime===null?16:clamp(now-lastTime,0,48);lastTime=now;
      lastPaint=now;
      if(!quiet())phase+=dt*.0003;
      const follow=1-Math.exp(-dt/100);
      pointer=pointer.map((v,i)=>v+(target[i]-v)*follow);
      hover=quiet()?0:hover+((pointing?1:0)-hover)*follow;
      variation=quiet()?seed:variation+(seed-variation)*(1-Math.exp(-dt/180));
      if(Math.abs(seed-variation)<.001)variation=seed;
      pulses=quiet()?[]:pulses.filter(p=>now-p.time<2400);
      const bounds=document.querySelector('.vault-hero-copy').getBoundingClientRect();
      const box=bounds.width?[bounds.left-30,bounds.top-25,bounds.right+35,bounds.bottom+30]:[-200,-200,-150,-150];
      engine.draw({width,height,dpr,matrix:camera(width,height,pointer[0]*hover,pointer[1]*hover),time:phase,seed:variation,
        pointer,hover,pulses,now,quietBox:box,light:root.dataset.theme==='light'});
      if(!quiet()&&(engine.kind==='webgl'||now<activeUntil||pulses.length||hover>.002&&!pointing))frame=requestAnimationFrame(render);
    }
    function wake() {
      if(disposed||contextLost)return;
      if(!visible()){cancelAnimationFrame(frame);frame=0;lastTime=null;lastPaint=-Infinity;pointing=false;hover=0;pulses=[];return;}
      if(!frame)frame=requestAnimationFrame(render);
    }
    function point(event){return [event.clientX/Math.max(width||window.innerWidth,1)*2-1,1-event.clientY/Math.max(height||window.innerHeight,1)*2];}
    function move(event){
      if(!visible()||quiet()||event.pointerType==='touch')return;
      if(event.target.closest(operating)){leave();return;}
      target=point(event);pointing=true;activeUntil=performance.now()+4500;wake();
    }
    function leave(){pointing=false;activeUntil=performance.now()+700;wake();}
    function emit(p){pulses.push({x:p[0],y:p[1],time:performance.now()});if(pulses.length>3)pulses.shift();activeUntil=performance.now()+4500;wake();}
    function click(event){if(visible()&&!quiet()&&!event.target.closest(operating))emit(point(event));}
    function key(event){if(['Enter',' '].includes(event.key)&&!event.repeat){event.preventDefault();if(visible()&&!quiet())emit([.35,0]);}}
    function lost(event){event.preventDefault();contextLost=true;cancelFade();cancelAnimationFrame(frame);frame=0;$('vault-art').dataset.renderer='fallback';controls();}
    function restored(){dispose();renderer=null;start();}
    function dispose(){
      disposed=true;cancelAnimationFrame(frame);engine.dispose();
      window.removeEventListener('pointermove',move);window.removeEventListener('click',click);window.removeEventListener('pointerleave',leave);
      stage.removeEventListener('pointerleave',leave);surface.removeEventListener('keydown',key);window.removeEventListener('resize',wake);
      canvas.removeEventListener('webglcontextlost',lost);canvas.removeEventListener('webglcontextrestored',restored);
    }
    window.addEventListener('pointermove',move,{passive:true});window.addEventListener('click',click);
    window.addEventListener('pointerleave',leave);stage.addEventListener('pointerleave',leave);surface.addEventListener('keydown',key);
    window.addEventListener('resize',wake,{passive:true});canvas.addEventListener('webglcontextlost',lost);canvas.addEventListener('webglcontextrestored',restored);
    return {wake,reset(){pointing=false;hover=0;pulses=[];lastTime=null;lastPaint=-Infinity;activeUntil=performance.now()+4500;wake();},dispose};
  }
  function start(){if(!renderer&&visible())renderer=createSpace();renderer?.wake();controls();}
  function refresh(){fallback();controls();start();renderer?.wake();}
  function init(){
    if(initialized||!$('vault-canvas'))return;initialized=true;
    $('vault-collection-btn').addEventListener('click',()=>showView('collection'));
    $('vault-review-btn').addEventListener('click',()=>showView('review',true));
    document.querySelectorAll('button[data-vault-scene]').forEach(button=>button.addEventListener('click',()=>{
      const next=button.dataset.vaultScene;if(next===scene)return;scene=next;write('steam-organizer-space-scene',scene);
      cancelFade();controls();fallback();renderer?.reset();
      if(!quiet()&&$('vault-art').dataset.renderer!=='fallback'&&typeof $('vault-canvas').animate==='function'){
        sceneAnimation=$('vault-canvas').animate([{opacity:.1},{opacity:1}],{duration:240,easing:'cubic-bezier(.2,.8,.2,1)'});
        sceneAnimation.onfinish=cancelFade;
      }
    }));
    $('vault-shuffle').addEventListener('click',()=>{seed+=2.3;fallback();renderer?.reset();});
    $('vault-pause').addEventListener('click',()=>{if(root.dataset.motion==='reduced')return;cancelFade();paused=!paused;write('steam-organizer-particles-paused',String(paused));controls();renderer?.reset();});
    $('quick-theme-btn').addEventListener('click',()=>queueMicrotask(refresh));$('theme-btn').addEventListener('click',()=>queueMicrotask(refresh));
    window.matchMedia('(prefers-color-scheme: light)').addEventListener?.('change',()=>queueMicrotask(refresh));
    window.addEventListener('organizer-state-change',queueSync);
    window.addEventListener('organizer-preview-ready',()=>{sync();showView('review');});
    window.addEventListener('organizer-appearance-change',()=>{cancelFade();queueSync();refresh();});window.addEventListener('organizer-motion-change',()=>{cancelFade();renderer?.reset();refresh();});
    document.addEventListener('visibilitychange',()=>{if(document.hidden)cancelFade();renderer?.wake();});
    forcedColors.addEventListener?.('change',()=>{cancelFade();refresh();});
    window.addEventListener('pagehide',()=>{cancelFade();renderer?.dispose();renderer=null;});window.addEventListener('pageshow',start);
    sync();showView('collection');refresh();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
