/* 줍줍알람 도구 계산기 (2026-11-20) — /tools/<slug>/ 의 [data-tool] 칸을 채운다.
   규칙 숫자를 바꾸면 site/tools.py 글(how·faq·CHECKED)도 같이 고칠 것. 입력값은 어디에도 저장하지 않는다. */
(function(){
  'use strict';
  var RATE = 3.00;                  // 한국은행 기준금리 (2026.8.27~) — tools.py BASE_RATE 와 같게
  var LEGAL = Math.min(10, RATE + 2); // 주택임대차보호법 시행령 제9조 전환율 상한

  /* ── 공통 ─────────────────────────────── */
  function man(v){ // 만원 → '6억 2,500만원'
    if(!isFinite(v)) return '-';
    var neg=v<0; v=Math.round(Math.abs(v));
    var e=Math.floor(v/10000), m=v%10000, s;
    if(e) s=e+'억'+(m?m.toLocaleString('ko-KR')+'만':'')+'원'; else s=m.toLocaleString('ko-KR')+'만원';
    return (neg?'−':'')+s;
  }
  function won(v){ return (v<0?'−':'')+Math.round(Math.abs(v)).toLocaleString('ko-KR')+'원'; }
  function pct(v,d){ return (Math.round(v*Math.pow(10,d||2))/Math.pow(10,d||2)).toLocaleString('ko-KR',{maximumFractionDigits:d||2})+'%'; }
  function num(s){ var v=parseFloat(String(s).replace(/,/g,'')); return isFinite(v)?v:0; }
  function esc(s){ return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
  function qs(){ var o={}; location.search.replace(/^\?/,'').split('&').forEach(function(kv){ if(!kv) return; var p=kv.split('='); o[decodeURIComponent(p[0])]=decodeURIComponent(p[1]||''); }); return o; }
  var Q=qs();

  function inp(label,key,val,unit,opt){ opt=opt||{};
    var v=(Q[key]!==undefined && opt.q)?Q[key]:val;
    return '<label class="g-row"><span>'+label+(opt.help?'<small class="t-help">'+opt.help+'</small>':'')+'</span><span class="g-in"><input type="text" inputmode="decimal" data-k="'+key+'" value="'+v+'" autocomplete="off"><em>'+unit+'</em></span>'+(unit==='만원'?'<small class="t-hint" data-h="'+key+'"></small>':'')+'</label>';
  }
  function seg(label,key,opts,def){
    return '<div class="g-row t-segrow"><span>'+label+'</span><span class="t-seg" role="group" aria-label="'+esc(label)+'" data-seg="'+key+'">'+
      opts.map(function(o,i){ return '<button type="button" data-v="'+o[0]+'" aria-pressed="'+(o[0]===def?'true':'false')+'">'+o[1]+'</button>'; }).join('')+'</span></div>';
  }
  function chk(label,key,def){ return '<label class="g-row t-chk"><span>'+label+'</span><input type="checkbox" data-k="'+key+'"'+(def?' checked':'')+'></label>'; }
  function picker(el){
    var raw=el.getAttribute('data-picks'); if(!raw) return '';
    var ps; try{ ps=JSON.parse(raw); }catch(e){ return ''; }
    if(!ps.length) return '';
    el._picks=ps;
    return '<label class="g-row t-pick"><span>지금 공고에서 불러오기<small class="t-help">접수 중·예정 공고의 타입별 최고 분양가</small></span><select data-pick><option value="">직접 입력</option>'+
      ps.map(function(p,i){ return '<option value="'+i+'">'+esc(p.t)+' · '+man(p.p)+'</option>'; }).join('')+'</select></label><p class="t-picked" data-picked hidden></p>';
  }
  function wire(el,run){
    function v(k){ var i=el.querySelector('[data-k="'+k+'"]'); if(!i) return 0; return i.type==='checkbox'?i.checked:num(i.value); }
    function s(k){ var b=el.querySelector('[data-seg="'+k+'"] [aria-pressed="true"]'); return b?b.getAttribute('data-v'):''; }
    function set(k,val){ var i=el.querySelector('[data-k="'+k+'"]'); if(i){ i.value=val; } }
    function hints(){ el.querySelectorAll('[data-h]').forEach(function(h){ var x=v(h.getAttribute('data-h')); h.textContent=x?'= '+man(x):''; }); }
    var api={v:v,s:s,set:set,out:function(sel,html){ var o=el.querySelector(sel); if(o) o.innerHTML=html; }};
    function go(){ hints(); try{ run(api); }catch(e){} }
    el.addEventListener('input',go); el.addEventListener('change',go);
    el.querySelectorAll('[data-seg]').forEach(function(g){ g.addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return;
      g.querySelectorAll('button').forEach(function(x){ x.setAttribute('aria-pressed', x===b?'true':'false'); }); go(); }); });
    var pk=el.querySelector('[data-pick]');
    if(pk) pk.addEventListener('change',function(){ var p=el._picks[pk.value], box=el.querySelector('[data-picked]');
      if(!p){ box.hidden=true; return; }
      set('price',p.p); if(p.a) set('area',p.a); if(p.r && el.querySelector('[data-k="dep"]')){ set('dep',p.r[0]); set('mid',p.r[1]); }
      box.innerHTML='<a href="'+p.u+'">'+esc(p.t)+'</a> 공고 값을 넣었어요'+(p.r?' (납부 비율 '+p.r.join('·')+'%)':'')+'. 금액은 그 타입의 최고 분양가예요.'; box.hidden=false; go(); });
    api.go=go; go(); return api;
  }
  function rows(list){ return '<table class="t-out"><tbody>'+list.map(function(r){ return '<tr'+(r[2]?' class="'+r[2]+'"':'')+'><th scope="row">'+r[0]+'</th><td>'+r[1]+'</td></tr>'; }).join('')+'</tbody></table>'; }
  function note(t){ return '<p class="g-toolnote">'+t+'</p>'; }

  var T={};

  /* ── 청약 가점 ─────────────────────────── */
  T['subscription-score']=function(el){
    var mu=['해당 없음 (집이 있거나 만 30세 전 미혼) · 0점','1년 미만 · 2점'],muv=[0,2],tg=['6개월 미만 · 1점','6개월 이상 ~ 1년 미만 · 2점'],tgv=[1,2],bu=[];
    for(var y=1;y<15;y++){ mu.push(y+'년 이상 ~ '+(y+1)+'년 미만 · '+(2*y+2)+'점'); muv.push(2*y+2); tg.push(y+'년 이상 ~ '+(y+1)+'년 미만 · '+(y+2)+'점'); tgv.push(y+2); }
    mu.push('15년 이상 · 32점'); muv.push(32); tg.push('15년 이상 · 17점'); tgv.push(17);
    for(var b=0;b<=6;b++) bu.push((b===6?'6명 이상':b+'명')+' · '+(5+5*b)+'점');
    var sp=['없음 · 0점'].concat(tg), spv=[0].concat(tgv);
    function sel(lab,key,opts,def){ return '<label class="g-row"><span>'+lab+'</span><select data-k="'+key+'">'+opts.map(function(o,i){ return '<option value="'+i+'"'+(i===def?' selected':'')+'>'+o+'</option>'; }).join('')+'</select></label>'; }
    el.innerHTML='<h2 class="t-h">내 청약 가점</h2>'+sel('무주택 기간','mu',mu,8)+sel('부양가족 수 (본인 제외)','bu',bu,2)+sel('내 청약통장 가입기간','tg',tg,10)+sel('배우자 청약통장 가입기간','sp',sp,0)+
      '<div class="g-res"><b data-t>0점</b><span data-d></span></div><div class="g-bar3"><i data-a></i><i data-b></i><i data-c></i></div><div data-o></div>'+
      note('점수표는 주택공급에 관한 규칙 별표 1 기준이에요. 배우자 통장은 그 점수의 절반(최대 3점)을 더하고 통장 칸 전체는 17점을 넘지 않아요. 최종 점수는 청약홈 \'청약가점 계산하기\'와 모집공고로 확인하세요.');
    wire(el,function(a){
      var A=muv[a.v('mu')], B=5+5*a.v('bu'), c0=tgv[a.v('tg')], add=Math.min(3,Math.floor(spv[a.v('sp')]/2)), C=Math.min(17,c0+add), t=A+B+C;
      el.querySelector('[data-t]').textContent=t+'점';
      el.querySelector('[data-d]').textContent='/ 84점 · 무주택 '+A+' + 부양가족 '+B+' + 통장 '+C+(add?' (배우자 +'+(C-c0)+')':'');
      el.querySelector('[data-a]').style.width=(A/84*100)+'%'; el.querySelector('[data-b]').style.width=(B/84*100)+'%'; el.querySelector('[data-c]').style.width=(C/84*100)+'%';
      var tip = t>=65?'서울 인기 단지에서도 해볼 만한 점수예요.':(t>=50?'수도권 대부분 단지의 커트라인 근처예요. 공고 페이지의 지난 당첨 가점과 비교해 보세요.':(t>=35?'가점제보다 추첨 물량(85㎡ 초과·비규제지역)이나 무순위를 노리는 편이 현실적이에요.':'가점으로는 어려워요. 무순위(줍줍)·추첨제·특별공급을 먼저 보세요.'));
      a.out('[data-o]','<p class="t-say">'+tip+' <a href="/lotto/">통장 없이 넣는 줍줍 공고 보기 →</a></p>');
    });
  };

  /* ── 1순위 ─────────────────────────────── */
  var DEP={seoul:[300,600,1000,1500],metro:[250,400,700,1000],other:[200,300,400,500]};
  T['subscription-priority']=function(el){
    el.innerHTML='<h2 class="t-h">1순위인지 확인</h2>'+
      seg('주택 종류','kind',[['private','민영주택'],['public','국민주택(공공분양)']],'private')+
      seg('공고 지역','zone',[['reg','투기과열·청약과열'],['cap','그 밖의 수도권'],['etc','수도권 밖']],'reg')+
      inp('청약통장 가입 기간','months',30,'개월')+
      '<div data-pub>'+inp('납입 인정 회차','times',30,'회')+chk('세대원 모두 무주택','nohouse',true)+'</div>'+
      '<div data-pri>'+seg('내가 사는 곳','live',[['seoul','서울·부산'],['metro','기타 광역시'],['other','기타 시·군']],'seoul')+
        seg('넣을 면적(전용)','size',[['0','85㎡ 이하'],['1','102㎡ 이하'],['2','135㎡ 이하'],['3','모든 면적']],'0')+inp('통장 예치금','deposit',300,'만원')+'</div>'+
      '<div data-reg>'+chk('세대주예요','head',true)+chk('세대원 모두 최근 5년 안에 당첨된 적 없음','nowin',true)+'<div data-pri2>'+chk('우리 세대 주택이 1채 이하','lt2',true)+'</div></div>'+
      '<div class="g-res"><b data-t></b><span data-d></span></div><div data-o></div>'+
      '<details class="t-more"><summary>납입 인정 금액 계산 (국민주택 저축총액)</summary>'+
        inp('2024년 10월까지 낸 회차','n1',24,'회')+inp('그때 한 달에 넣은 돈','a1',10,'만원')+inp('2024년 11월부터 낸 회차','n2',12,'회')+inp('지금 한 달에 넣는 돈','a2',25,'만원')+
        '<div class="g-res"><b data-sum></b><span data-sumd></span></div></details>'+
      note('주택공급에 관한 규칙 제27·28조, 별표 2 기준이에요. 시·도지사가 공고마다 기간·회차를 늘릴 수 있고(수도권 최대 24개월, 수도권 밖 최대 12개월) 지역 거주 기간 요건이 따로 붙으니 최종 기준은 모집공고문이에요.');
    wire(el,function(a){
      var kind=a.s('kind'), zone=a.s('zone'), reg=zone==='reg', need={reg:24,cap:12,etc:6}[zone];
      el.querySelector('[data-pub]').hidden=kind!=='public'; el.querySelector('[data-pri]').hidden=kind!=='private';
      el.querySelector('[data-reg]').hidden=!reg; el.querySelector('[data-pri2]').hidden=kind!=='private';
      var L=[], ok=true;
      function c(cond,txt){ L.push([cond?'✓':'✗',txt,cond?'t-ok':'t-no']); if(!cond) ok=false; }
      c(a.v('months')>=need,'가입 기간 '+need+'개월 이상 (지금 '+a.v('months')+'개월)');
      if(kind==='public'){ c(a.v('times')>=need,'납입 인정 '+need+'회 이상 (지금 '+a.v('times')+'회)'); c(a.v('nohouse'),'세대원 전원 무주택'); }
      else { var d=DEP[a.s('live')][+a.s('size')]; c(a.v('deposit')>=d,'예치금 '+man(d)+' 이상 (지금 '+man(a.v('deposit'))+')'); }
      if(reg){ c(a.v('head'),'세대주'); c(a.v('nowin'),'세대원 5년 내 당첨 이력 없음'); if(kind==='private') c(a.v('lt2'),'2주택 이상 소유 세대 아님'); }
      el.querySelector('[data-t]').textContent=ok?'1순위예요':'아직 2순위예요';
      el.querySelector('[data-t]').className=ok?'t-good':'t-bad';
      el.querySelector('[data-d]').textContent=ok?'공고문의 지역 거주 요건만 맞으면 1순위로 넣을 수 있어요':'✗ 표시된 조건을 채우면 1순위가 돼요';
      a.out('[data-o]','<ul class="t-checks">'+L.map(function(x){ return '<li class="'+x[2]+'"><b>'+x[0]+'</b> '+x[1]+'</li>'; }).join('')+'</ul>');
      var s1=a.v('n1')*Math.min(a.v('a1'),10), s2=a.v('n2')*Math.min(a.v('a2'),25);
      el.querySelector('[data-sum]').textContent=man(s1+s2);
      el.querySelector('[data-sumd]').textContent='인정 금액 (2024.10까지 회당 최대 10만원 '+man(s1)+' + 이후 회당 최대 25만원 '+man(s2)+')';
    });
  };

  /* ── 분양 대금 일정 ─────────────────────── */
  T['payment-plan']=function(el){
    el.innerHTML='<h2 class="t-h">언제 얼마가 필요할까</h2>'+picker(el)+
      inp('분양가','price',60000,'만원',{q:1})+inp('계약금 비율','dep',10,'%')+inp('중도금 비율','mid',60,'%',{help:'잔금 비율은 나머지로 자동'})+
      seg('중도금 내는 방법','loan',[['post','대출 · 이자 후불'],['free','대출 · 무이자'],['cash','내 현금(자납)']],'post')+
      inp('중도금 대출 금리','rate',4.5,'%')+inp('계약부터 입주까지','months',30,'개월')+inp('지금 쓸 수 있는 현금 (선택)','cash',0,'만원')+
      '<div data-o></div>'+note('중도금이 공사 기간에 고르게 나간다고 보고, 평균적으로 기간의 절반 동안 빌린 것으로 후불 이자를 추정했어요. 실제 회차·금액·대출 가능 여부는 입주자모집공고문의 \'공급금액 및 납부일정\'이 기준이에요.');
    wire(el,function(a){
      var P=a.v('price'), d=a.v('dep'), m=a.v('mid'), r=Math.max(0,100-d-m), D=P*d/100, M=P*m/100, R=P*r/100, loan=a.s('loan');
      var I= loan==='post' ? M*a.v('rate')/100*(a.v('months')/12)/2 : 0;
      var cashNow = D + (loan==='cash'?M:0), atMove=R+I;
      var L=[['계약 때 · 계약금 '+d+'%','<b>'+man(D)+'</b> <small>내 현금</small>'],
             ['공사 중 · 중도금 '+m+'%', man(M)+' <small>'+(loan==='cash'?'내 현금':'대출')+'</small>'],
             ['입주 때 · 잔금 '+r+'%', man(R)+' <small>주담대 전환 가능</small>']];
      if(I) L.push(['입주 때 · 중도금 후불 이자 (추정)', man(I)]);
      L.push(['입주 때 필요한 돈 합계','<b>'+man(atMove)+'</b> <small>+ 취득세·등기비</small>','t-sum']);
      var c=a.v('cash'), say='';
      if(c){ say = c>=cashNow ? '현금 '+man(c)+'으로 '+(loan==='cash'?'계약금·중도금':'계약금')+'을 낼 수 있어요. 남는 돈 '+man(c-cashNow)+'.' : (loan==='cash'?'계약금·중도금':'계약금')+'까지 '+man(cashNow-c)+'이 모자라요.'; }
      a.out('[data-o]','<div class="g-res"><b>'+man(cashNow)+'</b><span>지금 준비할 현금 ('+(loan==='cash'?'계약금+중도금':'계약금')+')</span></div>'+rows(L)+
        (say?'<p class="t-say">'+say+'</p>':'')+
        '<p class="t-next"><a href="/tools/acquisition-tax/?price='+Math.round(P)+'">이 분양가로 취득세 계산 →</a> <a href="/tools/loan-limit/?price='+Math.round(P)+'">잔금 대출 한도 보기 →</a></p>');
    });
  };

  /* ── 평·㎡ ─────────────────────────────── */
  var PY=400/121;
  T['area-converter']=function(el){
    el.innerHTML='<h2 class="t-h">평 ↔ ㎡</h2>'+inp('제곱미터','m2',84,'㎡')+inp('평','py',(84/PY).toFixed(2),'평')+
      '<div class="t-chips" data-chips>'+[39,49,59,74,84,101,114,135].map(function(x){ return '<button type="button" data-m="'+x+'">전용 '+x+'㎡</button>'; }).join('')+'</div><div data-o></div>'+
      note('1평 = 400/121㎡ ≈ 3.3058㎡. 공급면적(평형)은 단지마다 공용면적이 달라 \'추정\' 범위로만 보여 드려요. 정확한 값은 공고문 주택형별 면적표에 있어요.');
    var last='m2';
    el.addEventListener('input',function(e){ var k=e.target.getAttribute('data-k'); if(k) last=k; },true);
    el.querySelector('[data-chips]').addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; last='m2'; api.set('m2',b.getAttribute('data-m')); api.go(); });
    var api=wire(el,function(a){
      var m2,py;
      if(last==='py'){ py=a.v('py'); m2=py*PY; var i=el.querySelector('[data-k="m2"]'); if(document.activeElement!==i) i.value=+m2.toFixed(2); }
      else { m2=a.v('m2'); py=m2/PY; var j=el.querySelector('[data-k="py"]'); if(document.activeElement!==j) j.value=+py.toFixed(2); }
      a.out('[data-o]','<div class="g-res"><b>'+(+m2.toFixed(2)).toLocaleString('ko-KR')+'㎡ = '+(+py.toFixed(2)).toLocaleString('ko-KR')+'평</b></div>'+
        rows([['이 넓이가 전용면적이면','공급면적 약 '+Math.round(m2*1.30/PY)+'~'+Math.round(m2*1.36/PY)+'평형 <small>(추정)</small>'],['이 넓이가 공급면적이면','전용면적 약 '+Math.round(m2/1.36)+'~'+Math.round(m2/1.30)+'㎡ <small>(추정)</small>'],['평방피트','약 '+Math.round(m2*10.7639).toLocaleString('ko-KR')+' sq ft']]));
    });
  };

  /* ── 평당가 ─────────────────────────────── */
  T['price-per-pyeong']=function(el){
    el.innerHTML='<h2 class="t-h">평당가·㎡당 가격</h2>'+picker(el)+inp('가격 (분양가·매매가)','price',72700,'만원',{q:1})+inp('전용면적','area',84,'㎡',{q:1})+inp('공급면적 (선택)','supply',0,'㎡',{help:'공고문 면적표의 \'공급면적\''})+
      '<div data-o></div><details class="t-more"><summary>평당가로 총액 구하기</summary>'+inp('평당가','ppp',3000,'만원')+inp('면적','ppy',34,'평')+'<div class="g-res"><b data-rev></b><span>총액</span></div></details>'+
      note('분양가 \'3.3㎡당\'은 보통 공급면적 기준, 국토교통부 실거래가는 전용면적만 나와요. 비교할 때는 같은 기준끼리 보세요.');
    wire(el,function(a){
      var P=a.v('price'), ex=a.v('area'), sp=a.v('supply'), L=[];
      if(ex) L.push(['전용 기준 평당','<b>'+man(P/(ex/PY))+'</b>'],['전용 기준 ㎡당',man(P/ex)]);
      if(sp) L.push(['공급 기준 평당 (3.3㎡당)','<b>'+man(P/(sp/PY))+'</b>'],['공급 기준 ㎡당',man(P/sp)]);
      a.out('[data-o]',rows(L)+(ex?'':'<p class="t-say">면적을 넣어 주세요.</p>'));
      el.querySelector('[data-rev]').textContent=man(a.v('ppp')*a.v('ppy'));
    });
  };

  /* ── 전월세 전환 ─────────────────────────── */
  T['jeonse-monthly']=function(el){
    el.innerHTML='<h2 class="t-h">보증금 ↔ 월세</h2>'+seg('바꾸는 방향','mode',[['tomonth','전세 → 월세'],['tojeonse','월세 → 전세']],'tomonth')+
      '<div data-a>'+inp('지금 보증금','dep0',30000,'만원')+inp('바꾼 뒤 보증금','dep1',10000,'만원')+'</div>'+
      '<div data-b>'+inp('보증금','bdep',5000,'만원')+inp('월세','brent',100,'만원')+'</div>'+
      inp('전환율 (연)','rate',LEGAL.toFixed(1),'%',{help:'계약 중·갱신 때 법정 상한 연 '+LEGAL.toFixed(1)+'%'})+inp('비교: 전세대출 금리 (선택)','loan',0,'%')+
      '<div data-o></div>'+note('법정 상한 = min(연 10%, 한국은행 기준금리 '+RATE.toFixed(2)+'% + 연 2%) = 연 '+LEGAL.toFixed(1)+'% (주택임대차보호법 시행령 제9조). 새 계약에는 적용되지 않고, 공공임대는 공고별 전환 이율을 따라요.');
    wire(el,function(a){
      var mode=a.s('mode'), r=a.v('rate'); el.querySelector('[data-a]').hidden=mode!=='tomonth'; el.querySelector('[data-b]').hidden=mode==='tomonth';
      var warn = r>LEGAL+1e-9 ? '<p class="t-warn">연 '+pct(r,1)+'는 계약 중·갱신 때의 법정 상한(연 '+LEGAL.toFixed(1)+'%)보다 높아요. 새 계약이 아니면 상한까지만 적용돼요.</p>' : '';
      if(mode==='tomonth'){
        var diff=Math.max(0,a.v('dep0')-a.v('dep1')), rent=diff*r/100/12, cmp='';
        if(a.v('loan')) { var li=diff*a.v('loan')/100/12; cmp='<p class="t-say">그 '+man(diff)+'을 연 '+pct(a.v('loan'),2)+' 전세대출로 빌리면 이자가 월 '+man(li)+'이라, '+(li<rent?'전세(대출)가 월 '+man(rent-li)+' 덜 들어요.':'월세가 월 '+man(li-rent)+' 덜 들어요.')+'</p>'; }
        a.out('[data-o]','<div class="g-res"><b>월 '+man(rent)+'</b><span>보증금 '+man(diff)+'을 연 '+pct(r,2)+'로 바꾼 월세</span></div>'+warn+cmp);
      } else {
        var add=a.v('brent')*12/(r/100||1);
        a.out('[data-o]','<div class="g-res"><b>'+man(a.v('bdep')+add)+'</b><span>전세로 환산한 보증금 (월세 '+man(a.v('brent'))+' → 보증금 '+man(add)+')</span></div>'+warn);
      }
    });
  };

  /* ── 대출 이자 ─────────────────────────── */
  function amort(P,rY,yrs,g){ // 원리금균등, 거치 g년
    var r=rY/1200, n=Math.round(yrs*12), gm=Math.round(g*12), k=n-gm; if(k<=0) return {first:P*r,total:P*r*n,pay:P*r};
    var pay=r>0?P*r/(1-Math.pow(1+r,-k)):P/k; return {pay:pay,grace:P*r,total:P*r*gm+pay*k-P};
  }
  T['loan-interest']=function(el){
    el.innerHTML='<h2 class="t-h">상환 방식별 비교</h2>'+inp('대출 금액','amt',30000,'만원')+inp('금리 (연)','rate',4.0,'%')+inp('기간','yrs',30,'년')+inp('거치 기간 (선택)','grace',0,'년',{help:'이자만 내는 기간'})+'<div data-o></div>'+
      note('고정금리로 끝까지 간다고 보고 계산한 값이에요. 변동금리는 금리가 바뀌는 때부터 상환액이 다시 계산돼요. 원 단위는 만원 아래에서 반올림했어요.');
    wire(el,function(a){
      var P=a.v('amt'), R=a.v('rate'), Y=a.v('yrs'), G=Math.min(a.v('grace'),Y-0.5), r=R/1200, n=Math.round(Y*12), gm=Math.round(G*12), k=n-gm;
      if(!(P>0&&Y>0)) return;
      var e=amort(P,R,Y,G);
      var pFirst=P/k+P*r, pTotal=P*r*gm+r*P*(k+1)/2;
      var bTotal=P*r*n;
      var tb=[]; var bal=P, cum=0;
      for(var mth=1;mth<=n;mth++){ var it=bal*r, pr=mth<=gm?0:e.pay-it; cum+=it; bal-=pr; if(mth%60===0||mth===n) tb.push([Math.round(mth/12)+'년 뒤', man(Math.max(0,bal)), man(cum)]); }
      a.out('[data-o]','<div class="t-cards">'+
        '<div><span>원리금균등</span><b>월 '+man(e.pay)+'</b><small>'+(gm?'거치 중 월 '+man(e.grace)+' · ':'')+'총이자 '+man(e.total)+'</small></div>'+
        '<div><span>원금균등</span><b>첫 달 '+man(pFirst)+'</b><small>점점 줄어요 · 총이자 '+man(pTotal)+'</small></div>'+
        '<div><span>만기일시</span><b>월 '+man(P*r)+'</b><small>만기에 원금 '+man(P)+' · 총이자 '+man(bTotal)+'</small></div></div>'+
        '<table class="t-out t-yr"><thead><tr><th>원리금균등</th><th>남은 원금</th><th>낸 이자 누계</th></tr></thead><tbody>'+tb.map(function(x){ return '<tr><th scope="row">'+x[0]+'</th><td>'+x[1]+'</td><td>'+x[2]+'</td></tr>'; }).join('')+'</tbody></table>');
    });
  };

  /* ── 주담대 한도 ─────────────────────────── */
  T['loan-limit']=function(el){
    el.innerHTML='<h2 class="t-h">내 주담대 한도</h2>'+seg('집이 있는 곳','zone',[['reg','규제지역 (서울 전역 등)'],['cap','수도권 비규제'],['etc','지방']],'reg')+chk('생애최초 구입 (LTV 70%)','first',false)+
      inp('집값 (시세·분양가)','price',90000,'만원',{q:1})+inp('연소득 (세전, 부부 합산 가능)','inc',7000,'만원')+inp('다른 대출의 1년 원리금','oth',0,'만원')+
      inp('대출 금리','rate',4.2,'%')+inp('스트레스 금리','st',3.0,'%p',{help:'한도 계산에만 더해요'})+inp('만기','yrs',30,'년')+inp('LTV','ltv',40,'%')+inp('DSR 한도','dsr',40,'%')+
      '<div data-o></div>'+note('원리금균등 상환으로 단순 계산한 참고값이에요. 소득 인정 방식, 은행 심사, 정책대출 여부에 따라 실제 한도는 달라요. 규제지역 지정·스트레스 금리는 정책에 따라 바뀌니 대출 전 은행에서 확인하세요.');
    var lastZone='', lastFirst=null;
    wire(el,function(a){
      var z=a.s('zone'), f=a.v('first');
      if(z!==lastZone||f!==lastFirst){ a.set('ltv', f?70:(z==='reg'?40:70)); a.set('st', z==='etc'?0.75:3.0); lastZone=z; lastFirst=f; }
      var P=a.v('price'), r=(a.v('rate')+a.v('st'))/1200, n=a.v('yrs')*12, ann=r>0?12*r/(1-Math.pow(1+r,-n)):12/n;
      var dsr=Math.max(0,(a.v('inc')*a.v('dsr')/100-a.v('oth'))/ann), ltv=P*a.v('ltv')/100;
      var cap = z==='etc'?Infinity:(P<=150000?60000:(P<=250000?40000:20000));
      var m=Math.min(dsr,ltv,cap), by = m===cap?'지역 금액 상한':(m===ltv?'LTV':'DSR');
      a.out('[data-o]','<div class="g-res"><b>'+man(m)+'</b><span>'+by+' 기준이 가장 작아서 이 값이 한도예요</span></div>'+
        '<div class="t-cards"><div'+(by==='LTV'?' class="on"':'')+'><span>LTV '+a.v('ltv')+'%</span><b>'+man(ltv)+'</b></div><div'+(by==='DSR'?' class="on"':'')+'><span>DSR '+a.v('dsr')+'% (금리 '+pct(a.v('rate')+a.v('st'),2)+')</span><b>'+man(dsr)+'</b></div>'+
        '<div'+(by==='지역 금액 상한'?' class="on"':'')+'><span>수도권·규제지역 상한</span><b>'+(cap===Infinity?'없음':man(cap))+'</b></div></div>'+
        '<p class="t-say">집값 '+man(P)+' 중 대출 '+man(m)+'을 빼면 내 돈 <b>'+man(Math.max(0,P-m))+'</b>이 필요해요 (취득세 별도).</p>');
    });
  };

  /* ── 취득세 ─────────────────────────────── */
  T['acquisition-tax']=function(el){
    el.innerHTML='<h2 class="t-h">주택 취득세</h2>'+picker(el)+inp('취득가액 (분양가·매매가)','price',60000,'만원',{q:1})+
      seg('사고 나면 몇 채','houses',[['1','1주택'],['2','2주택'],['3','3주택'],['4','4주택 이상']],'1')+
      chk('새로 사는 집이 조정대상지역','adj',false)+chk('전용 85㎡ 초과','big',false)+'<div data-tmp>'+chk('일시적 2주택 (종전 집을 기한 안에 팔 예정)','tmp',false)+'</div>'+
      '<div data-fst>'+chk('생애최초 구입 (본인·배우자 집 가진 적 없음)','first',false)+'</div>'+inp('전용면적 (선택, 85㎡ 판단용)','area',0,'㎡',{q:1})+
      '<div data-o></div>'+note('지방세법 제11조·제13조의2, 지방세특례제한법 제36조의3 기준(2026.11.20 확인)이에요. 분양 아파트는 주택 수를 분양 계약일 기준으로 세요. 공시가격 1억원 이하 주택 등 주택 수 제외 특례, 법인·증여·상속은 계산하지 않아요.');
    wire(el,function(a){
      var P=a.v('price'), h=+a.s('houses'), adj=a.v('adj'), ar=a.v('area'), big=ar?ar>85:a.v('big');
      if(ar){ var bb=el.querySelector('[data-k="big"]'); bb.checked=ar>85; }
      el.querySelector('[data-tmp]').hidden=h!==2; el.querySelector('[data-fst]').hidden=h!==1;
      var std;
      if(P<=60000) std=1; else if(P<=90000) std=Math.round((P/10000*2/3-3)*10000)/10000; else std=3;
      var rate, heavy=false;
      if(h===1||(h===2&&a.v('tmp'))) rate=std;
      else if(adj){ rate=h===2?8:12; heavy=true; }
      else { if(h===2) rate=std; else { rate=h===3?8:12; heavy=true; } }
      var tax=P*rate/100, edu=heavy?P*0.004:tax*0.1, agr=big?P*(heavy?(rate===8?0.006:0.01):0.002):0;
      var cut=0; if(a.v('first')&&h===1&&P<=120000) cut=Math.min(tax,200);
      var tot=tax-cut+edu+agr;
      var L=[['적용 세율',pct(rate,4)+(heavy?' <small>중과</small>':'')],['취득세',man(tax)],['지방교육세',man(edu)],['농어촌특별세',big?man(agr):'없음 <small>(85㎡ 이하)</small>']];
      if(cut) L.push(['생애최초 감면','− '+man(cut)]);
      L.push(['합계','<b>'+man(tot)+'</b> <small>취득가액의 '+pct(tot/P*100,2)+'</small>','t-sum']);
      var say = a.v('first')&&h===1&&P>120000 ? '<p class="t-warn">12억원을 넘으면 생애최초 감면을 받을 수 없어요.</p>':'';
      a.out('[data-o]','<div class="g-res"><b>'+man(tot)+'</b><span>잔금일부터 60일 안에 신고·납부</span></div>'+rows(L)+say);
    });
  };

  /* ── 중개보수 ─────────────────────────────── */
  var SALE=[[5000,0.6,25],[20000,0.5,80],[90000,0.4,0],[120000,0.5,0],[150000,0.6,0],[1e12,0.7,0]];
  var LEASE=[[5000,0.5,20],[10000,0.4,30],[60000,0.3,0],[120000,0.4,0],[150000,0.5,0],[1e12,0.6,0]];
  T['brokerage-fee']=function(el){
    el.innerHTML='<h2 class="t-h">중개보수 상한</h2>'+seg('거래','type',[['sale','매매'],['jeonse','전세'],['month','월세']],'sale')+seg('물건','obj',[['house','주택·아파트'],['op','오피스텔 (85㎡ 이하·부엌·욕실)']],'house')+
      inp('매매가·보증금','amt',80000,'만원')+'<div data-rent>'+inp('월세','rent',50,'만원')+'</div>'+seg('부가세','vat',[['10','일반과세 10%'],['0','넣지 않음']],'10')+
      '<div data-o></div>'+note('공인중개사법 시행규칙 제20조와 서울·경기 조례 요율표(상한) 기준이에요. 상한 안에서 협의해 정하고, 거래 양쪽이 각각 내요. 간이과세 중개사의 부가세는 이보다 낮아요.');
    wire(el,function(a){
      var t=a.s('type'), o=a.s('obj'), A=a.v('amt'); el.querySelector('[data-rent]').hidden=t!=='month';
      var base=A, how='';
      if(t==='month'){ base=A+a.v('rent')*100; how='보증금 + 월세×100'; if(base<5000){ base=A+a.v('rent')*70; how='보증금 + 월세×70 (5천만원 미만이라 다시 계산)'; } }
      var rate, lim=0;
      if(o==='op'){ rate=t==='sale'?0.5:0.4; }
      else { var tb=t==='sale'?SALE:LEASE; for(var i=0;i<tb.length;i++){ if(base<tb[i][0]){ rate=tb[i][1]; lim=tb[i][2]; break; } } }
      var fee=base*10000*rate/100; if(lim) fee=Math.min(fee,lim*10000);
      fee=Math.floor(fee); var vat=a.s('vat')==='10'?Math.floor(fee*0.1):0;
      a.out('[data-o]','<div class="g-res"><b>'+won(fee+vat)+'</b><span>최대 지급액 (부가세 포함)</span></div>'+
        rows([['거래금액'+(how?' <small>'+how+'</small>':''),man(base)],['상한요율',pct(rate,1)+(lim?' <small>한도 '+man(lim)+'</small>':'')],['중개보수',won(fee)],['부가세',won(vat)],['합계','<b>'+won(fee+vat)+'</b>','t-sum']]));
    });
  };

  document.querySelectorAll('[data-tool]').forEach(function(el){ var f=T[el.getAttribute('data-tool')]; if(f){ el.innerHTML=''; f(el); } });
})();
