#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil
import sys
import re
import subprocess
import tempfile

TARGET = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("index.html")
MARKER = "SCENERY_CALIBRATION_V1"

if not TARGET.exists():
    raise SystemExit(f"[ERROR] {TARGET} tidak ditemukan. Jalankan script ini dari root repo coc-village-generator.")

text = TARGET.read_text(encoding="utf-8")
if MARKER in text:
    print("[OK] Scenery calibration sudah terpasang; tidak ada perubahan baru.")
    raise SystemExit(0)


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[ERROR] Patch '{label}' mengharapkan 1 match, ketemu {count}. File mungkin sudah berubah dari branch scenery-calibration yang dibaca ChatGPT.")
    text = text.replace(old, new, 1)
    print(f"[OK] {label}")

# 1) Toolbar controls
old = '''      <select id="scenerySelect" style="width:auto;min-width:190px"></select>
      <input id="sceneryFile" type="file" accept="image/*" style="display:none;width:auto;max-width:220px">
      <div class="spacer"></div>'''
new = '''      <select id="scenerySelect" style="width:auto;min-width:190px"></select>
      <input id="sceneryFile" type="file" accept="image/*" style="display:none;width:auto;max-width:220px">
      <button id="calibrateScenery" class="ghost" style="display:none">Calibrate Scenery</button>
      <button id="exportCalibrations" class="ghost" style="display:none">Export Calibrations</button>
      <button id="saveCalibration" style="display:none">Save Calibration</button>
      <button id="resetCalibration" class="ghost" style="display:none">Reset</button>
      <button id="cancelCalibration" class="ghost" style="display:none">Cancel</button>
      <div class="spacer"></div>'''
replace_once(old, new, "toolbar controls")

# 2) State
old = '''let current=null, referenceComponents=[], parsedVillage=null; let previewMode='master'; let zoom=1; let showGrid=true; let buildingRoll=0; let layoutRoll=0; let customScenery=null;
let hoverState=null; let dragState=null; let sceneryImage=null; let sceneryReady=false; let sceneryFrame=null;'''
new = '''let current=null, referenceComponents=[], parsedVillage=null; let previewMode='master'; let zoom=1; let showGrid=true; let buildingRoll=0; let layoutRoll=0; let customScenery=null; let customSceneryKey='custom';
let hoverState=null; let dragState=null; let sceneryImage=null; let sceneryReady=false; let sceneryFrame=null;

// SCENERY_CALIBRATION_V1 - 4-corner bilinear grid calibration.
const CALIBRATION_STORAGE_KEY='coc-scenery-calibrations-v1';
const CALIBRATION_CORNERS=['top','right','bottom','left'];
const DEFAULT_CALIBRATION_GRID={top:[.5,.18],right:[.82,.5],bottom:[.5,.82],left:[.18,.5]};
let calibrationState=null;'''
replace_once(old, new, "calibration state")

# 3) Helpers
anchor = '''function masterMetrics(){const W=canvas.width,H=canvas.height,gw=current?.grid?.width||44,gh=current?.grid?.height||44,pad=58,cs=Math.floor(Math.min((W-pad*2)/gw,(H-pad*2)/gh)),ox=Math.floor((W-cs*gw)/2),oy=Math.floor((H-cs*gh)/2);return{W,H,gw,gh,cs,ox,oy}}'''
helpers = r'''function calCloneGrid(grid){return Object.fromEntries(CALIBRATION_CORNERS.map(k=>[k,[Number(grid[k][0]),Number(grid[k][1])]]))}
function calValidGrid(grid){return!!grid&&CALIBRATION_CORNERS.every(k=>Array.isArray(grid[k])&&grid[k].length>=2&&Number.isFinite(Number(grid[k][0]))&&Number.isFinite(Number(grid[k][1])))}
function loadCalibrationMap(){try{const raw=JSON.parse(localStorage.getItem(CALIBRATION_STORAGE_KEY)||'{}');return raw&&typeof raw==='object'?raw:{}}catch{return{}}}
function persistCalibrationMap(map){try{localStorage.setItem(CALIBRATION_STORAGE_KEY,JSON.stringify(map))}catch(err){console.warn('Calibration storage gagal:',err)}}
function currentSceneryKey(){const kind=$('scenerySelect')?.value||'classic';return kind==='custom'?customSceneryKey:kind}
function defaultGridForSelectedScenery(){const kind=$('scenerySelect')?.value||'classic';if(kind==='custom'||kind==='sakura')return calCloneGrid(DEFAULT_CALIBRATION_GRID);const grid=window.GameAssetPack?.sceneryInfo(kind)?.grid;return calValidGrid(grid)?calCloneGrid(grid):calCloneGrid(DEFAULT_CALIBRATION_GRID)}
function effectiveGridForSelectedScenery(){const key=currentSceneryKey();if(calibrationState?.key===key&&calValidGrid(calibrationState.draftGrid))return calibrationState.draftGrid;const saved=loadCalibrationMap()[key];return calValidGrid(saved)?calCloneGrid(saved):defaultGridForSelectedScenery()}
function selectedSceneryImage(){const kind=$('scenerySelect')?.value||'classic';if(kind==='custom')return customScenery;if(kind==='sakura')return sceneryReady?sceneryImage:null;return window.GameAssetPack?.scenery(kind)||null}
function screenGridCorners(frame,grid){const map=([x,y])=>({x:frame.x+x*frame.w,y:frame.y+y*frame.h});return{top:map(grid.top),right:map(grid.right),bottom:map(grid.bottom),left:map(grid.left)}}
function bilinearPoint(corners,u,v){const a=(1-u)*(1-v),b=u*(1-v),c=u*v,d=(1-u)*v;return{x:a*corners.top.x+b*corners.right.x+c*corners.bottom.x+d*corners.left.x,y:a*corners.top.y+b*corners.right.y+c*corners.bottom.y+d*corners.left.y}}
function bilinearInverse(corners,p){const t=corners.top,r=corners.right,l=corners.left;const ax=r.x-t.x,ay=r.y-t.y,bx=l.x-t.x,by=l.y-t.y,det=ax*by-ay*bx;let u=.5,v=.5;if(Math.abs(det)>1e-8){const px=p.x-t.x,py=p.y-t.y;u=(px*by-py*bx)/det;v=(ax*py-ay*px)/det}for(let i=0;i<10;i++){const q=bilinearPoint(corners,u,v),fx=q.x-p.x,fy=q.y-p.y;const dux=(1-v)*(corners.right.x-corners.top.x)+v*(corners.bottom.x-corners.left.x),duy=(1-v)*(corners.right.y-corners.top.y)+v*(corners.bottom.y-corners.left.y),dvx=(1-u)*(corners.left.x-corners.top.x)+u*(corners.bottom.x-corners.right.x),dvy=(1-u)*(corners.left.y-corners.top.y)+u*(corners.bottom.y-corners.right.y),jdet=dux*dvy-duy*dvx;if(Math.abs(jdet)<1e-9)break;const du=(fx*dvy-fy*dvx)/jdet,dv=(dux*fy-duy*fx)/jdet;u-=du;v-=dv;if(Math.abs(du)+Math.abs(dv)<1e-7)break}return{u,v}}
function calibrationFrame(){return calibrationState?.frame||sceneryFrame}
function updateCalibrationControls(){const inScenery=previewMode==='scenery',active=!!calibrationState;const set=(id,show)=>{const el=$(id);if(el)el.style.display=show?'':'none'};set('calibrateScenery',inScenery&&!active);set('exportCalibrations',inScenery&&!active);set('saveCalibration',inScenery&&active);set('resetCalibration',inScenery&&active);set('cancelCalibration',inScenery&&active);if($('scenerySelect'))$('scenerySelect').disabled=active;if($('sceneryFile'))$('sceneryFile').disabled=active;canvas.style.cursor=active?'crosshair':''}
function beginCalibration(){if(previewMode!=='scenery')setPreviewMode('scenery');drawCanvas();const image=selectedSceneryImage();if(!image||!sceneryFrame){alert('Scenery belum siap. Tunggu asset selesai loading atau pilih/upload image dulu.');return}const key=currentSceneryKey(),grid=effectiveGridForSelectedScenery();calibrationState={key,draftGrid:calCloneGrid(grid),frame:{x:sceneryFrame.x,y:sceneryFrame.y,w:sceneryFrame.w,h:sceneryFrame.h},draggingCorner:null,hoverCorner:null};$('hoverCard').style.display='none';hoverState=null;updateCalibrationControls();drawCanvas()}
function saveCalibration(){if(!calibrationState)return;const map=loadCalibrationMap();map[calibrationState.key]=calCloneGrid(calibrationState.draftGrid);persistCalibrationMap(map);calibrationState=null;updateCalibrationControls();render()}
function resetCalibration(){if(!calibrationState)return;calibrationState.draftGrid=defaultGridForSelectedScenery();calibrationState.draggingCorner=null;calibrationState.hoverCorner=null;drawCanvas()}
function cancelCalibration(){if(!calibrationState)return;calibrationState=null;updateCalibrationControls();render()}
function exportCalibrations(){const calibrations=loadCalibrationMap(),keys=Object.keys(calibrations);if(!keys.length){alert('Belum ada calibration yang disimpan.');return}const payload={type:'coc-scenery-calibrations',version:1,generatedAt:new Date().toISOString(),calibrations},blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='scenery-calibrations.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function calibrationHandleAt(p){if(!calibrationState)return null;const frame=calibrationFrame();if(!frame)return null;const corners=screenGridCorners(frame,calibrationState.draftGrid);let hit=null,best=26;for(const k of CALIBRATION_CORNERS){const d=Math.hypot(p.x-corners[k].x,p.y-corners[k].y);if(d<best){best=d;hit=k}}return hit}
function moveCalibrationCorner(corner,p){const frame=calibrationFrame();if(!frame||!corner)return;const nx=Math.max(0,Math.min(1,(p.x-frame.x)/frame.w)),ny=Math.max(0,Math.min(1,(p.y-frame.y)/frame.h));calibrationState.draftGrid[corner]=[nx,ny]}
function drawCalibrationOverlay(){if(!calibrationState||previewMode!=='scenery')return;const frame=calibrationFrame();if(!frame)return;const corners=screenGridCorners(frame,calibrationState.draftGrid),colors={top:'#FADCD5',right:'#D7A8B6',bottom:'#B88698',left:'#8FA8C9'};ctx.save();ctx.lineWidth=3;ctx.strokeStyle='rgba(250,220,213,.92)';ctx.setLineDash([10,7]);ctx.beginPath();ctx.moveTo(corners.top.x,corners.top.y);ctx.lineTo(corners.right.x,corners.right.y);ctx.lineTo(corners.bottom.x,corners.bottom.y);ctx.lineTo(corners.left.x,corners.left.y);ctx.closePath();ctx.stroke();ctx.setLineDash([]);for(const k of CALIBRATION_CORNERS){const p=corners[k],hot=calibrationState.draggingCorner===k||calibrationState.hoverCorner===k;ctx.beginPath();ctx.arc(p.x,p.y,hot?15:12,0,Math.PI*2);ctx.fillStyle=colors[k];ctx.fill();ctx.lineWidth=hot?4:2;ctx.strokeStyle=hot?'#fff':'rgba(27,12,26,.92)';ctx.stroke();ctx.font='800 12px Inter, sans-serif';ctx.textAlign='center';ctx.textBaseline='bottom';ctx.fillStyle='#fff';ctx.fillText(k.toUpperCase(),p.x,p.y-18)}roundRect(ctx,28,28,490,48,12,'rgba(27,12,26,.84)','rgba(250,220,213,.32)');ctx.fillStyle='#FADCD5';ctx.font='700 13px Inter, sans-serif';ctx.textAlign='left';ctx.textBaseline='middle';ctx.fillText('Drag TOP / RIGHT / BOTTOM / LEFT ke empat sudut area grid village.',44,52);ctx.restore()}
function handleCalibrationPointerMove(e,p){if(!calibrationState)return false;if(calibrationState.draggingCorner){moveCalibrationCorner(calibrationState.draggingCorner,p);calibrationState.hoverCorner=calibrationState.draggingCorner;canvas.style.cursor='grabbing';drawCanvas();return true}calibrationState.hoverCorner=calibrationHandleAt(p);canvas.style.cursor=calibrationState.hoverCorner?'grab':'crosshair';drawCanvas();return true}

'''
if anchor not in text:
    raise SystemExit("[ERROR] Anchor masterMetrics tidak ditemukan.")
text = text.replace(anchor, helpers + anchor, 1)
print("[OK] calibration helpers")

# 4) 4-corner metrics + mapping
old = '''function isoMetrics(){const W=canvas.width,H=canvas.height,gw=current?.grid?.width||44,gh=current?.grid?.height||44;if(sceneryFrame?.grid){const map=([x,y])=>({x:sceneryFrame.x+x*sceneryFrame.w,y:sceneryFrame.y+y*sceneryFrame.h}),top=map(sceneryFrame.grid.top),right=map(sceneryFrame.grid.right),bottom=map(sceneryFrame.grid.bottom),left=map(sceneryFrame.grid.left),tw=Math.max(8,Math.abs(right.x-left.x)*2/gw),th=Math.max(6,Math.abs(bottom.y-top.y)*2/gh);return{W,H,gw,gh,tw,th,ox:top.x,oy:top.y,corners:{top,right,bottom,left}}}const tw=Math.min(24,Math.floor((W-160)/gw)),th=tw/2,ox=W/2,oy=Math.max(70,Math.floor((H-gh*th)/2));return{W,H,gw,gh,tw,th,ox,oy}}'''
new = '''function isoMetrics(){const W=canvas.width,H=canvas.height,gw=current?.grid?.width||44,gh=current?.grid?.height||44;if(sceneryFrame?.grid){const corners=screenGridCorners(sceneryFrame,sceneryFrame.grid),{top,right,bottom,left}=corners,tw=Math.max(8,Math.abs(right.x-left.x)*2/gw),th=Math.max(6,Math.abs(bottom.y-top.y)*2/gh);return{W,H,gw,gh,tw,th,ox:top.x,oy:top.y,corners}}const tw=Math.min(24,Math.floor((W-160)/gw)),th=tw/2,ox=W/2,oy=Math.max(70,Math.floor((H-gh*th)/2));return{W,H,gw,gh,tw,th,ox,oy}}'''
replace_once(old, new, "isoMetrics 4-corner")

old = '''function isoPoint(m,x,y){if(m.corners){const{top,right,left}=m.corners;return{x:top.x+(right.x-top.x)*(x/m.gw)+(left.x-top.x)*(y/m.gh),y:top.y+(right.y-top.y)*(x/m.gw)+(left.y-top.y)*(y/m.gh)}}return{x:m.ox+(x-y)*(m.tw/2),y:m.oy+(x+y)*(m.th/2)}}'''
new = '''function isoPoint(m,x,y){if(m.corners)return bilinearPoint(m.corners,x/m.gw,y/m.gh);return{x:m.ox+(x-y)*(m.tw/2),y:m.oy+(x+y)*(m.th/2)}}'''
replace_once(old, new, "bilinear isoPoint")

# 5) Scenery rendering
old = '''function drawContainedImage(img,W,H){const scale=Math.min(W/img.naturalWidth,H/img.naturalHeight),w=img.naturalWidth*scale,h=img.naturalHeight*scale,x=(W-w)/2,y=(H-h)/2;ctx.drawImage(img,x,y,w,h);return{x,y,w,h}}'''
new = '''function drawContainedImage(img,W,H){const scale=Math.min(W/img.naturalWidth,H/img.naturalHeight),w=img.naturalWidth*scale,h=img.naturalHeight*scale,x=(W-w)/2,y=(H-h)/2;ctx.drawImage(img,x,y,w,h);return{x,y,w,h}}
function drawImageAtFrame(img,frame){ctx.drawImage(img,frame.x,frame.y,frame.w,frame.h);return{x:frame.x,y:frame.y,w:frame.w,h:frame.h}}'''
replace_once(old, new, "frozen calibration frame")

old = '''function drawSceneryBackground(){const W=canvas.width,H=canvas.height,kind=$('scenerySelect').value;sceneryFrame=null;ctx.fillStyle='#102c3a';ctx.fillRect(0,0,W,H);if(kind==='custom'&&customScenery){const frame=drawContainedImage(customScenery,W,H);sceneryFrame={...frame,grid:null};return}if(kind==='sakura'&&sceneryReady){drawContainedImage(sceneryImage,W,H);ctx.fillStyle='rgba(24,10,20,.18)';ctx.fillRect(0,0,W,H);return}const info=window.GameAssetPack?.sceneryInfo(kind),image=window.GameAssetPack?.scenery(kind);if(info&&image){const frame=drawCalibratedImage(image,W,H,info.grid);sceneryFrame={...frame,grid:info.grid};return}drawHomeVillageFallback(W,H)}'''
new = '''function drawSceneryBackground(){const W=canvas.width,H=canvas.height,kind=$('scenerySelect').value,key=currentSceneryKey(),grid=effectiveGridForSelectedScenery();sceneryFrame=null;ctx.fillStyle='#102c3a';ctx.fillRect(0,0,W,H);if(kind==='custom'&&customScenery){const frame=calibrationState?.key===key&&calibrationState.frame?drawImageAtFrame(customScenery,calibrationState.frame):drawContainedImage(customScenery,W,H);sceneryFrame={...frame,grid};return}if(kind==='sakura'&&sceneryReady){const frame=calibrationState?.key===key&&calibrationState.frame?drawImageAtFrame(sceneryImage,calibrationState.frame):drawContainedImage(sceneryImage,W,H);ctx.fillStyle='rgba(24,10,20,.18)';ctx.fillRect(0,0,W,H);sceneryFrame={...frame,grid};return}const info=window.GameAssetPack?.sceneryInfo(kind),image=window.GameAssetPack?.scenery(kind);if(info&&image){const frame=calibrationState?.key===key&&calibrationState.frame?drawImageAtFrame(image,calibrationState.frame):drawCalibratedImage(image,W,H,grid);sceneryFrame={...frame,grid};return}drawHomeVillageFallback(W,H)}'''
replace_once(old, new, "calibrated scenery rendering")

old = '''function drawScenery(){ctx.clearRect(0,0,canvas.width,canvas.height);drawSceneryBackground();const m=isoMetrics();if(showGrid)for(let y=0;y<m.gh;y++)for(let x=0;x<m.gw;x++)drawIsoTile(m,x,y,'rgba(255,255,255,.025)',.20);if(current?.walls){const arr=current.walls.slice().sort((a,b)=>(a.x+a.y)-(b.x+b.y));for(const w of arr)drawIsoWall(w,m)}if(current?.buildings){const list=current.buildings.map((b,i)=>({...b,_i:i})).sort((a,b)=>(a.x+a.y+a.w+a.h)-(b.x+b.y+b.w+b.h));for(const b of list)drawIsoBuilding(b,m)}if(dragState?.candidate&&previewMode==='scenery')drawIsoGhost(dragState,m)}'''
new = '''function drawScenery(){ctx.clearRect(0,0,canvas.width,canvas.height);drawSceneryBackground();const m=isoMetrics();if(showGrid)for(let y=0;y<m.gh;y++)for(let x=0;x<m.gw;x++)drawIsoTile(m,x,y,'rgba(255,255,255,.025)',.20);if(current?.walls){const arr=current.walls.slice().sort((a,b)=>(a.x+a.y)-(b.x+b.y));for(const w of arr)drawIsoWall(w,m)}if(current?.buildings){const list=current.buildings.map((b,i)=>({...b,_i:i})).sort((a,b)=>(a.x+a.y+a.w+a.h)-(b.x+b.y+b.w+b.h));for(const b of list)drawIsoBuilding(b,m)}if(dragState?.candidate&&previewMode==='scenery')drawIsoGhost(dragState,m);drawCalibrationOverlay()}'''
replace_once(old, new, "calibration overlay")

# 6) Inverse pointer mapping
old = '''function isoGridFromPoint(p){const m=isoMetrics(),a=(p.x-m.ox)/(m.tw/2),b=(p.y-m.oy)/(m.th/2);return{x:Math.floor((a+b)/2),y:Math.floor((b-a)/2)}}'''
new = '''function isoGridFromPoint(p){const m=isoMetrics();if(m.corners){const uv=bilinearInverse(m.corners,p);return{x:Math.floor(uv.u*m.gw),y:Math.floor(uv.v*m.gh)}}const a=(p.x-m.ox)/(m.tw/2),b=(p.y-m.oy)/(m.th/2);return{x:Math.floor((a+b)/2),y:Math.floor((b-a)/2)}}'''
replace_once(old, new, "bilinear inverse pointer mapping")

# 7) Pointer handlers
old = '''canvas.addEventListener('pointermove',e=>{if(!current)return;const p=canvasPoint(e),g=pointToGrid(p);if(dragState){const b=current.buildings[dragState.index],x=g.x-dragState.offsetX,y=g.y-dragState.offsetY,valid=canMoveBuilding(dragState.index,x,y);dragState.candidate={x,y};dragState.valid=valid;$('dragGhost').style.display='block';$('dragGhost').textContent=valid?`Move to ${x}, ${y}`:'Blocked';$('dragGhost').style.color=valid?'#bff3cc':'#ffc0cc';const sr=$('previewStage').getBoundingClientRect();$('dragGhost').style.left=(e.clientX-sr.left+14)+'px';$('dragGhost').style.top=(e.clientY-sr.top+14)+'px';drawCanvas();return}showHover(e,g);drawCanvas()});
canvas.addEventListener('pointerleave',()=>{$('hoverCard').style.display='none';hoverState=null;if(!dragState)drawCanvas()});
canvas.addEventListener('pointerdown',e=>{if(!current)return;const p=canvasPoint(e),g=pointToGrid(p),i=findBuildingAt(g);if(i<0)return;const b=current.buildings[i];dragState={index:i,offsetX:g.x-b.x,offsetY:g.y-b.y,candidate:{x:b.x,y:b.y},valid:true,original:{x:b.x,y:b.y}};canvas.setPointerCapture?.(e.pointerId);$('hoverCard').style.display='none';drawCanvas()});
canvas.addEventListener('pointerup',e=>{if(!dragState)return;const b=current.buildings[dragState.index];if(dragState.valid&&dragState.candidate){b.x=dragState.candidate.x;b.y=dragState.candidate.y}dragState=null;$('dragGhost').style.display='none';updateOutput();render()});
canvas.addEventListener('pointercancel',()=>{dragState=null;$('dragGhost').style.display='none';drawCanvas()});'''
new = '''canvas.addEventListener('pointermove',e=>{if(!current)return;const p=canvasPoint(e);if(calibrationState&&previewMode==='scenery'){handleCalibrationPointerMove(e,p);return}const g=pointToGrid(p);if(dragState){const b=current.buildings[dragState.index],x=g.x-dragState.offsetX,y=g.y-dragState.offsetY,valid=canMoveBuilding(dragState.index,x,y);dragState.candidate={x,y};dragState.valid=valid;$('dragGhost').style.display='block';$('dragGhost').textContent=valid?`Move to ${x}, ${y}`:'Blocked';$('dragGhost').style.color=valid?'#bff3cc':'#ffc0cc';const sr=$('previewStage').getBoundingClientRect();$('dragGhost').style.left=(e.clientX-sr.left+14)+'px';$('dragGhost').style.top=(e.clientY-sr.top+14)+'px';drawCanvas();return}showHover(e,g);drawCanvas()});
canvas.addEventListener('pointerleave',()=>{if(calibrationState){calibrationState.hoverCorner=null;if(!calibrationState.draggingCorner)canvas.style.cursor='crosshair';drawCanvas();return}$('hoverCard').style.display='none';hoverState=null;if(!dragState)drawCanvas()});
canvas.addEventListener('pointerdown',e=>{if(!current)return;const p=canvasPoint(e);if(calibrationState&&previewMode==='scenery'){const hit=calibrationHandleAt(p);if(hit){calibrationState.draggingCorner=hit;calibrationState.hoverCorner=hit;canvas.setPointerCapture?.(e.pointerId);canvas.style.cursor='grabbing';drawCanvas()}return}const g=pointToGrid(p),i=findBuildingAt(g);if(i<0)return;const b=current.buildings[i];dragState={index:i,offsetX:g.x-b.x,offsetY:g.y-b.y,candidate:{x:b.x,y:b.y},valid:true,original:{x:b.x,y:b.y}};canvas.setPointerCapture?.(e.pointerId);$('hoverCard').style.display='none';drawCanvas()});
canvas.addEventListener('pointerup',e=>{if(calibrationState){calibrationState.draggingCorner=null;canvas.releasePointerCapture?.(e.pointerId);canvas.style.cursor=calibrationState.hoverCorner?'grab':'crosshair';drawCanvas();return}if(!dragState)return;const b=current.buildings[dragState.index];if(dragState.valid&&dragState.candidate){b.x=dragState.candidate.x;b.y=dragState.candidate.y}dragState=null;$('dragGhost').style.display='none';updateOutput();render()});
canvas.addEventListener('pointercancel',()=>{if(calibrationState){calibrationState.draggingCorner=null;calibrationState.hoverCorner=null;canvas.style.cursor='crosshair';drawCanvas();return}dragState=null;$('dragGhost').style.display='none';drawCanvas()});'''
replace_once(old, new, "calibration pointer handling")

# 8) Preview mode
old = '''function setPreviewMode(mode){previewMode=mode;$('modeMaster').classList.toggle('active',mode==='master');$('modeScenery').classList.toggle('active',mode==='scenery');$('scenerySelect').style.display=mode==='scenery'?'':'none';$('sceneryFile').style.display=(mode==='scenery'&&$('scenerySelect').value==='custom')?'':'none';render()}'''
new = '''function setPreviewMode(mode){if(calibrationState&&mode!=='scenery')calibrationState=null;previewMode=mode;$('modeMaster').classList.toggle('active',mode==='master');$('modeScenery').classList.toggle('active',mode==='scenery');$('scenerySelect').style.display=mode==='scenery'?'':'none';$('sceneryFile').style.display=(mode==='scenery'&&$('scenerySelect').value==='custom')?'':'none';updateCalibrationControls();render()}'''
replace_once(old, new, "preview mode controls")

# 9) Scenery events
old = '''$('scenerySelect').addEventListener('change',()=>{$('sceneryFile').style.display=$('scenerySelect').value==='custom'?'':'none';render()});$('sceneryFile').addEventListener('change',e=>{const f=e.target.files?.[0];if(!f)return;const img=new Image();img.onload=()=>{customScenery=img;render()};img.src=URL.createObjectURL(f)});'''
new = '''$('scenerySelect').addEventListener('change',()=>{$('sceneryFile').style.display=$('scenerySelect').value==='custom'?'':'none';updateCalibrationControls();render()});$('sceneryFile').addEventListener('change',e=>{const f=e.target.files?.[0];if(!f)return;const url=URL.createObjectURL(f),img=new Image();img.onload=()=>{customScenery=img;customSceneryKey=`custom:${f.name}:${img.naturalWidth}x${img.naturalHeight}`;URL.revokeObjectURL(url);render()};img.src=url});
$('calibrateScenery').addEventListener('click',beginCalibration);$('saveCalibration').addEventListener('click',saveCalibration);$('resetCalibration').addEventListener('click',resetCalibration);$('cancelCalibration').addEventListener('click',cancelCalibration);$('exportCalibrations').addEventListener('click',exportCalibrations);'''
replace_once(old, new, "scenery calibration events")

# 10) Init
old = '''populateSceneryOptions();referenceComponents=decomposeComponents(REFERENCE_DATA);sceneryImage=new Image();sceneryImage.onload=()=>{sceneryReady=true;render()};sceneryImage.src=SAKURA_BG;clearParsedVillage();setZoom(1);generateFull();'''
new = '''populateSceneryOptions();updateCalibrationControls();referenceComponents=decomposeComponents(REFERENCE_DATA);sceneryImage=new Image();sceneryImage.onload=()=>{sceneryReady=true;render()};sceneryImage.src=SAKURA_BG;clearParsedVillage();setZoom(1);generateFull();'''
replace_once(old, new, "initial calibration controls")

backup = TARGET.with_suffix(TARGET.suffix + ".scenery-calibration.bak")
if not backup.exists():
    shutil.copy2(TARGET, backup)
    print(f"[OK] Backup: {backup}")

TARGET.write_text(text, encoding="utf-8")

node = shutil.which("node")
if node:
    inline_scripts = [m for m in re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", text, flags=re.S | re.I) if m.strip()]
    if inline_scripts:
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tmp:
            tmp.write("\n".join(inline_scripts))
            tmp_path = Path(tmp.name)
        checked = subprocess.run([node, "--check", str(tmp_path)], capture_output=True, text=True)
        tmp_path.unlink(missing_ok=True)
        if checked.returncode != 0:
            print("[ERROR] node --check menemukan syntax error. Mengembalikan index.html ke backup.")
            if backup.exists():
                shutil.copy2(backup, TARGET)
            print(checked.stderr.strip())
            raise SystemExit(2)
        print("[OK] node --check: JavaScript valid")
else:
    print("[WARN] Node.js tidak ditemukan, jadi syntax check JS dilewati.")

print(f"[DONE] 4-point scenery calibration berhasil dipasang ke {TARGET}")
print("       Test: buka app -> Scenery -> Calibrate Scenery -> drag 4 marker -> Save Calibration.")
print("       Undo cepat: git checkout -- index.html")
