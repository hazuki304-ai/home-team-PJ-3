(() => {
  const startBtn = document.getElementById("track-start");
  if (!startBtn) return;
  const stopBtn = document.getElementById("track-stop");
  const saveBtn = document.getElementById("save-location-now");
  const status = document.getElementById("location-status");
  const coords = document.getElementById("coords");
  const elapsed = document.getElementById("elapsed");
  const tag = document.getElementById("location-tag");
  let watchId = null, latest = null, startedAt = null, lastPosition = null, stayStarted = null;
  let stayTimer = null, ticker = null, lastSaved = 0;

  function formatSeconds(s) {
    const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = s%60;
    return [h,m,sec].map(v => String(v).padStart(2,"0")).join(":");
  }
  async function savePosition(position, staySeconds, label) {
    const p = position.coords;
    const response = await fetch("/api/locations", {
      method:"POST", headers:{"Content-Type":"application/json","X-CSRFToken":window.CSRF_TOKEN},
      body:JSON.stringify({latitude:p.latitude,longitude:p.longitude,stay_time:staySeconds,tag:label || tag.value || "手動記録"})
    });
    if (!response.ok) throw new Error("記録の保存に失敗しました");
  }
  function distanceMeters(a,b) {
    const R=6371000, rad=x=>x*Math.PI/180;
    const dLat=rad(b.latitude-a.latitude), dLon=rad(b.longitude-a.longitude);
    const x=Math.sin(dLat/2)**2+Math.cos(rad(a.latitude))*Math.cos(rad(b.latitude))*Math.sin(dLon/2)**2;
    return 2*R*Math.asin(Math.sqrt(x));
  }
  function stop() {
    if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    watchId=null; clearInterval(ticker); clearTimeout(stayTimer);
    startBtn.disabled=false; stopBtn.disabled=true; saveBtn.disabled=true;
    status.textContent="停止中。位置情報の取得は終了しました。";
  }
  startBtn.addEventListener("click", () => {
    if (!navigator.geolocation) { status.textContent="このブラウザは位置情報に対応していません。"; return; }
    if (!window.isSecureContext) { status.textContent="位置情報にはHTTPS接続（またはlocalhost）が必要です。"; return; }
    startedAt=Date.now(); lastPosition=null; stayStarted=null; latest=null;
    startBtn.disabled=true; stopBtn.disabled=false;
    status.textContent="位置情報の許可を待っています…";
    ticker=setInterval(()=>{ if(startedAt) elapsed.textContent=formatSeconds(Math.floor((Date.now()-startedAt)/1000)); },1000);
    watchId=navigator.geolocation.watchPosition(async pos=>{
      latest=pos; const p=pos.coords;
      coords.textContent=`${p.latitude.toFixed(6)}, ${p.longitude.toFixed(6)}`;
      saveBtn.disabled=false;
      status.textContent=`取得中（精度 約${Math.round(p.accuracy)}m）`;
      if (!lastPosition || distanceMeters(lastPosition,p)>50) {
        clearTimeout(stayTimer);
        lastPosition={latitude:p.latitude,longitude:p.longitude};
        stayStarted=Date.now();
        stayTimer=setTimeout(async()=>{
          if (latest && stayStarted && Date.now()-stayStarted>=30000) {
            try { await savePosition(latest,Math.floor((Date.now()-stayStarted)/1000),"自動記録"); status.textContent="滞在記録を保存しました（取得は継続中）。"; }
            catch(e){ status.textContent=e.message; }
          }
        },30000);
      }
    }, err=>{
      const msgs={1:"位置情報の利用が許可されませんでした。",2:"位置情報を取得できません。",3:"位置情報の取得がタイムアウトしました。"};
      status.textContent=msgs[err.code] || "位置情報の取得に失敗しました。";
      stop();
    },{enableHighAccuracy:true,maximumAge:5000,timeout:20000});
  });
  stopBtn.addEventListener("click",stop);
  saveBtn.addEventListener("click",async()=>{
    if(!latest) return;
    try { await savePosition(latest,stayStarted?Math.floor((Date.now()-stayStarted)/1000):0,tag.value||"手動記録"); status.textContent="現在地を記録しました。"; }
    catch(e){ status.textContent=e.message; }
  });
  document.getElementById("clear-locations").addEventListener("click",async()=>{
    if(!confirm("自分の位置情報記録をすべて削除します。この操作は取り消せません。")) return;
    const r=await fetch("/api/locations/clear",{method:"POST",headers:{"X-CSRFToken":window.CSRF_TOKEN}});
    if(r.ok) location.reload(); else status.textContent="削除に失敗しました。";
  });
  window.addEventListener("pagehide",stop);
})();
