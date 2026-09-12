(function(){
  const CODES={en:'eng.1',fr:'fra.1',es:'esp.1',de:'ger.1',it:'ita.1',sa:'ksa.1'};
  const norm=s=>(s||'').toString().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
  const pair=(a,b)=>[norm(a),norm(b)].sort().join('|');
  function stateOf(c){const t=(c?.status?.type?.state||c?.status?.type?.name||c?.status?.type?.description||'').toString().toLowerCase();if(/post|final|completed|full time|ft/.test(t))return'post';if(/in|live|progress|half|ht/.test(t))return'in';return'pre';}
  function scoreOf(x){const v=x?.score;if(v===undefined||v===null||v==='')return null;if(typeof v==='object')return v.displayValue??v.value??null;return v;}
  function visibleScore(h,a){const hs=scoreOf(h),as=scoreOf(a);return hs!==null&&as!==null?String(hs)+'-'+String(as):null;}
  function ensureTrainingOption(){
    try{
      const selects=[...document.querySelectorAll('select')];
      for(const s of selects){
        const text=norm([...s.options].map(o=>o.textContent||'').join(' '));
        if(!/(championnat|competition|tournoi)/.test(text))continue;
        if([...s.options].some(o=>norm(o.textContent)==='entrainement'))return true;
        const o=document.createElement('option');o.value='training';o.textContent='Entraînement';s.appendChild(o);return true;
      }
    }catch(e){}
    return false;
  }
  function stateRank(s){return s==='post'?3:s==='in'?2:1;}
  function applyFeed(code,j){
    try{
      if(typeof fixtures==='undefined'||!Array.isArray(fixtures))return 0;
      const league=Object.entries(CODES).find(([,v])=>v===code)?.[0]||'';
      let hits=0;
      for(const ev of (j?.events||[]))for(const c of (ev?.competitions||[])){
        const cs=c?.competitors||[];
        const h=cs.find(x=>x.homeAway==='home')||cs[0],a=cs.find(x=>x.homeAway==='away')||cs[1];
        const hn=h?.team?.displayName||h?.team?.shortDisplayName||h?.athlete?.displayName||'';
        const an=a?.team?.displayName||a?.team?.shortDisplayName||a?.athlete?.displayName||'';
        if(!hn||!an)continue;
        const k=pair(hn,an),incoming=stateOf(c),detail=c?.status?.type?.shortDetail||c?.status?.type?.detail||'',score=visibleScore(h,a);
        for(const f of fixtures){
          if(f?.l!==league||pair(f?.h,f?.a)!==k)continue;
          const finalLocked=f._atlasVerifiedFinal===true;
          const current=f._atlasLiveState||'pre';
          const st=finalLocked&&incoming!=='post'?'post':(stateRank(incoming)<stateRank(current)&&current==='post'?'post':incoming);
          f._atlasLiveState=st;
          f._atlasLiveDetail=detail;
          f._atlasLiveUpdatedAt=new Date().toISOString();
          f._atlasStatusLabel=st==='post'?'Terminé':st==='in'?'En cours':'À venir';
          if(score!==null&&(st==='in'||st==='post')){f._atlasLiveScore=score;f.s=score;}
          if(st==='post'){
            f._atlasVerifiedFinal=true;
            if(score!==null)f._atlasFinalScore=score;
            else if(f._atlasFinalScore)f.s=f._atlasFinalScore;
          }
          hits++;
        }
      }
      return hits;
    }catch(e){return 0}
  }
  async function load(){
    ensureTrainingOption();
    const feed={};let providersOk=0,matchesUpdated=0,totalEvents=0;
    await Promise.all(Object.values(CODES).map(async code=>{
      try{
        const r=await fetch(`../data/football-${code}.json?ts=${Date.now()}`,{cache:'no-store'});
        if(!r.ok)throw new Error('HTTP '+r.status);
        const j=await r.json();feed[code]=j;providersOk++;totalEvents+=(j?.events||[]).length;matchesUpdated+=applyFeed(code,j);
      }catch(e){feed[code]={error:String(e),events:[]};}
    }));
    window.ATLAS_FOOT_SOURCE_FEED=feed;
    window.ATLAS_FOOT_LIVE_STATUS={ok:providersOk>0,updatedAt:new Date().toISOString(),providersOk,totalEvents,matchesUpdated,source:'ATLAS same-origin broker · resilient loader',rules:{threeStatesOnly:true,scoreAloneNeverFinal:true,liveScoreVisible:true,finalLock:true,trainingOption:true}};
    try{if(typeof window.ATLAS_FOOT_APPLY_SOURCE_FEED==='function')window.ATLAS_FOOT_APPLY_SOURCE_FEED(feed)}catch(e){}
    try{if(typeof render==='function')render()}catch(e){}
    ensureTrainingOption();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(load,50),{once:true});else setTimeout(load,50);
  setInterval(load,60000);
})();
