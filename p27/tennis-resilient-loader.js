(function(){
 const norm=s=>(s||'').toString().normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
 const stateOf=c=>{const s=(c?.status?.type?.state||'pre').toLowerCase();return s==='post'?'post':s==='in'?'in':'pre'};
 const label=s=>s==='post'?'Terminé':s==='in'?'En cours':'À venir';
 const score=x=>{const v=x?.score;if(v===undefined||v===null||v==='')return null;return typeof v==='object'?(v.displayValue??v.value??null):v};
 function feedFixtures(j){const out=[];for(const ev of(j?.events||[]))for(const c of(ev?.competitions||[])){const cs=c?.competitors||[];const h=cs.find(x=>x.homeAway==='home')||cs[0],a=cs.find(x=>x.homeAway==='away')||cs[1];const hn=h?.athlete?.displayName||h?.team?.displayName||h?.displayName||'',an=a?.athlete?.displayName||a?.team?.displayName||a?.displayName||'';if(!hn||!an)continue;const st=stateOf(c),hs=score(h),as=score(a);out.push({id:ev?.id||c?.id||`${hn}-${an}`,h:hn,a:an,d:ev?.date||c?.date||'',tour:c?.type?.text||c?.notes?.[0]?.headline||ev?.season?.slug||'Tennis',_atlasLiveState:st,_atlasStatusLabel:label(st),_atlasLiveScore:hs!==null&&as!==null?`${hs}-${as}`:null,_atlasSource:'tennis-feed',_atlasUpdatedAt:j?.generatedAt||new Date().toISOString()});}return out}
 async function load(){try{const r=await fetch('../data/tennis-feed.json?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);const j=await r.json(),fresh=feedFixtures(j);window.ATLAS_TENNIS_SOURCE_FEED=j;window.ATLAS_TENNIS_LIVE_STATUS={ok:true,updatedAt:j.generatedAt||new Date().toISOString(),matches:fresh.length,source:j.source||'ATLAS Tennis feed',rules:{threeStatesOnly:true,scoreAloneNeverFinal:true,feedDrivesDisplayedFixtures:true}};
   if(typeof fixtures!=='undefined'&&Array.isArray(fixtures)){fixtures.splice(0,fixtures.length,...fresh);try{if(typeof render==='function')render()}catch(e){}}
   try{if(typeof window.ATLAS_TENNIS_APPLY_SOURCE_FEED==='function')window.ATLAS_TENNIS_APPLY_SOURCE_FEED(j,fresh)}catch(e){}
 }catch(e){window.ATLAS_TENNIS_LIVE_STATUS={ok:false,error:String(e),updatedAt:new Date().toISOString()}}
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(load,50),{once:true});else setTimeout(load,50);setInterval(load,60000);
})();
