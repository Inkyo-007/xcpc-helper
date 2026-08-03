import{g as T,H as l,I as x,J as e,K as w,L as p,M as ye,F as z,N as E,O as q,P as M,Q as D,S as pe,R as ve,U as xe,V as f,W as O,X as me,Y as j,Z as _e,_ as ne,$ as se,a0 as ie,r as $,a1 as X,a2 as Q,a3 as ke,a4 as we,o as fe,w as ee,b as ge,a5 as $e,f as H,c as P,a6 as Ce,x as W,y as Ne,a7 as Me,u as je,a8 as Pe}from"./vendor-vue-DhP9QW9z.js";import{N as Se,a as oe,b as Oe,c as qe,d as ze,B as Ee,e as Te,f as Le,z as Ae,g as He,l as Ue,h as Be}from"./vendor-naive-CEJo4fWO.js";import{E as F,H as Ie,t as k,a as le,l as Fe,h as Re,b as Ve,d as De,c as Ge,k as Ke,e as Ye,f as Je,s as Xe,g as We}from"./vendor-codemirror-CE1_HSv7.js";(function(){const o=document.createElement("link").relList;if(o&&o.supports&&o.supports("modulepreload"))return;for(const r of document.querySelectorAll('link[rel="modulepreload"]'))d(r);new MutationObserver(r=>{for(const c of r)if(c.type==="childList")for(const m of c.addedNodes)m.tagName==="LINK"&&m.rel==="modulepreload"&&d(m)}).observe(document,{childList:!0,subtree:!0});function s(r){const c={};return r.integrity&&(c.integrity=r.integrity),r.referrerPolicy&&(c.referrerPolicy=r.referrerPolicy),r.crossOrigin==="use-credentials"?c.credentials="include":r.crossOrigin==="anonymous"?c.credentials="omit":c.credentials="same-origin",c}function d(r){if(r.ep)return;r.ep=!0;const c=s(r);fetch(r.href,c)}})();const R=[{id:"templates",label:"模板整理",icon:"template",children:[{id:"tpl-lib",label:"模板库",page:"lib"},{id:"tpl-books",label:"打印册",page:"books"},{id:"tpl-io",label:"导入 / 导出",page:"io"}]},{id:"contest",label:"比赛工具",icon:"timer",badge:"规划中",children:[{id:"stress",label:"对拍器",page:"stress"},{id:"gen",label:"数据生成",page:"gen"}]},{id:"settings",label:"设置",icon:"settings",badge:"规划中",page:"settings"}],re={books:{group:"模板整理",sub:"打印册",icon:"book",title:"打印册",hint:"勾选模板、拖拽排序，一键生成带目录的 Markdown 与 PDF。此功能在 M2 里程碑实现。"},io:{group:"模板整理",sub:"导入 / 导出",icon:"import",title:"导入 / 导出",hint:"批量导入本地目录（目录自动映射为分类），或整库备份 / 迁移。此功能在 M2 里程碑实现。"},stress:{group:"比赛工具",sub:"对拍器",icon:"timer",title:"对拍器",hint:"规划中：挂上暴力与正解，随机数据自动对拍。"},gen:{group:"比赛工具",sub:"数据生成",icon:"timer",title:"数据生成",hint:"规划中：按约束生成随机测试数据。"},settings:{group:"设置",sub:"",icon:"settings",title:"设置",hint:"规划中：数据目录、备份策略、默认语言等。"}},Ze={class:"sidebar"},Qe={class:"brand"},et={class:"brand-mark"},tt={class:"nav-scroll","aria-label":"功能导航"},at=["onClick"],nt={class:"nav-label"},st={key:0,class:"nav-badge"},it={key:0,class:"nav-sub"},ot=["onClick"],lt=T({__name:"SideNav",props:{activePage:{},openGroups:{}},emits:["navigate","toggle"],setup(t,{emit:o}){const s=t,d=o,r={template:xe,timer:ve,settings:pe};function c(u){var g;return u.page===s.activePage?!0:((g=u.children)==null?void 0:g.some(b=>b.page===s.activePage))??!1}function m(u){u.children?d("toggle",u.id):u.page&&d("navigate",u.page)}return(u,g)=>(l(),x("aside",Ze,[e("div",Qe,[e("span",et,[w(p(ye),{size:17,"stroke-width":2.5})]),g[0]||(g[0]=e("span",{class:"brand-name"},"XCPC Helper",-1)),g[1]||(g[1]=e("span",{class:"brand-ver"},"v0.2",-1))]),e("nav",tt,[(l(!0),x(z,null,E(p(R),b=>(l(),x("div",{key:b.id,class:q(["nav-group",{open:t.openGroups[b.id]}])},[e("button",{type:"button",class:q(["nav-item",{active:c(b)}]),onClick:v=>m(b)},[(l(),M(D(r[b.icon]),{size:17})),e("span",nt,f(b.label),1),b.badge?(l(),x("span",st,f(b.badge),1)):O("",!0),b.children?(l(),M(p(me),{key:1,class:"nav-chev",size:14})):O("",!0)],10,at),b.children?(l(),x("div",it,[(l(!0),x(z,null,E(b.children,v=>(l(),x("button",{key:v.id,type:"button",class:q(["nav-sub-item",{active:t.activePage===v.page}]),onClick:h=>d("navigate",v.page)},[g[2]||(g[2]=e("span",{class:"sub-dot"},null,-1)),e("span",null,f(v.label),1)],10,ot))),128))])):O("",!0)],2))),128))]),g[3]||(g[3]=e("div",{class:"sidebar-foot"},[e("span",{class:"status-dot","aria-hidden":"true"}),e("span",null,"本地模式 · 数据保存在本机")],-1))]))}}),rt={class:"topbar"},ct={class:"crumb"},dt={class:"page-title"},ut={class:"page-sub"},pt={class:"top-actions"},vt={class:"hue-pop"},mt={class:"hue-pop-head"},ft={class:"hue-value"},gt={class:"hue-presets"},ht=["title","onClick"],bt=["aria-label"],yt={class:"theme-menu"},xt=["onClick"],_t=T({__name:"TopBar",props:{pageMeta:{},mode:{},modeIcon:{},modeLabel:{},hue:{}},emits:["cycle-theme","set-mode","set-hue"],setup(t,{emit:o}){const s=o,d=$(!1),r=$(!1),c=[12,25,45,90,160,200,260,320],m={sun:ie,moon:se,monitor:ne},u=[{value:"light",label:"亮色",icon:ie},{value:"dark",label:"暗色",icon:se},{value:"system",label:"跟随系统",icon:ne}];function g(v){s("set-hue",v)}function b(v){s("set-mode",v),r.value=!1}return(v,h)=>(l(),x("header",rt,[e("div",ct,[e("h1",dt,f(t.pageMeta.group),1),e("span",ut,f(t.pageMeta.sub?`/ ${t.pageMeta.sub}`:""),1)]),e("div",pt,[w(p(oe),{show:d.value,offset:10,placement:"bottom-end",trigger:"click","onUpdate:show":h[1]||(h[1]=_=>d.value=_)},{trigger:j(()=>[e("button",{type:"button",class:"icon-btn","aria-label":"调整主题色相",title:"调整主题色相",onClick:h[0]||(h[0]=_=>d.value=!d.value)},[w(p(_e),{size:17})])]),default:j(()=>[e("div",vt,[e("div",mt,[h[4]||(h[4]=e("span",null,"主题色相",-1)),e("span",ft,f(t.hue)+"°",1)]),w(p(Se),{value:t.hue,min:0,max:360,step:1,"onUpdate:value":g},null,8,["value"]),e("div",gt,[(l(),x(z,null,E(c,_=>e("button",{key:_,type:"button",class:q(["swatch",{active:_===t.hue}]),style:X({background:`hsl(${_} 60% 50%)`}),title:`色相 ${_}°`,onClick:C=>g(_)},null,14,ht)),64))])])]),_:1},8,["show"]),w(p(oe),{show:r.value,offset:10,placement:"bottom-end",trigger:"hover","content-style":"padding: 4px","onUpdate:show":h[3]||(h[3]=_=>r.value=_)},{trigger:j(()=>[e("button",{type:"button",class:"icon-btn theme-btn","aria-label":`切换主题，当前 ${t.modeLabel}`,onClick:h[2]||(h[2]=_=>s("cycle-theme"))},[(l(),M(D(m[t.modeIcon]),{size:17}))],8,bt)]),default:j(()=>[e("div",yt,[(l(),x(z,null,E(u,_=>e("button",{key:_.value,type:"button",class:q(["theme-option",{active:t.mode===_.value}]),onClick:C=>b(_.value)},[(l(),M(D(_.icon),{size:15})),e("span",null,f(_.label),1),t.mode===_.value?(l(),M(p(Q),{key:0,size:14,class:"theme-check"})):O("",!0)],10,xt)),64))])]),_:1},8,["show"])])]))}}),kt={class:"placeholder-page"},wt={class:"ph-icon"},$t={class:"ph-title"},Ct={class:"ph-hint"},Nt=T({__name:"PlaceholderPage",props:{page:{},meta:{}},setup(t){const o={book:we,import:ke,timer:ve,settings:pe};return(s,d)=>(l(),x("div",kt,[e("div",wt,[(l(),M(D(o[t.meta.icon]),{size:27}))]),e("h2",$t,f(t.meta.title),1),e("p",Ct,f(t.meta.hint),1),d[0]||(d[0]=e("span",{class:"ph-milestone"},"M2 里程碑规划中",-1))]))}}),V=[{id:"all",name:"全部",hue:null},{id:"ds",name:"数据结构",hue:160},{id:"graph",name:"图论",hue:25},{id:"string",name:"字符串",hue:280},{id:"math",name:"数学",hue:200},{id:"dp",name:"动态规划",hue:340},{id:"misc",name:"其他",hue:80}];function he(t){return V.find(o=>o.id===t)??V[V.length-1]}function Mt(t){return he(t).hue??160}const jt={class:"code-view"},Pt={class:"code-head"},St={class:"code-status"},Ot={class:"code-file"},qt={class:"code-lang"},zt={class:"code-lines"},Et=T({__name:"CodeView",props:{code:{},file:{},lang:{}},setup(t,{expose:o}){const s=t,d=$(null),r=$(!1),c=$(0),m=P(()=>s.code.split(`
`).length);let u=null,g=0;const b=F.theme({"&":{backgroundColor:"transparent",color:"var(--code-text)",fontSize:"13px"},"&.cm-focused":{outline:"none"},".cm-scroller":{fontFamily:"var(--font-mono)",lineHeight:"1.7",overflow:"hidden"},".cm-content":{padding:"12px 0 20px",caretColor:"var(--accent)"},".cm-line":{padding:"0 16px 0 8px"},".cm-gutters":{backgroundColor:"transparent",border:"none",color:"var(--code-ln)",fontFamily:"var(--font-mono)",fontSize:"11px"},".cm-activeLine":{backgroundColor:"rgb(255 255 255 / 0.035)"},".cm-activeLineGutter":{backgroundColor:"transparent",color:"var(--accent)"},".cm-selectionBackground, &.cm-focused .cm-selectionBackground":{backgroundColor:"rgb(255 255 255 / 0.12)"},"&.cm-focused .cm-cursor":{borderLeftColor:"var(--accent)"}}),v=Ie.define([{tag:k.keyword,color:"var(--code-kw)"},{tag:[k.string,k.special(k.string)],color:"var(--code-string)"},{tag:[k.number,k.bool,k.null],color:"var(--code-number)"},{tag:[k.comment,k.lineComment,k.blockComment],color:"var(--code-comment)",fontStyle:"italic"},{tag:[k.meta,k.macroName,k.definition(k.macroName)],color:"var(--code-preproc)"},{tag:[k.typeName,k.className,k.namespace],color:"#86b8b1"},{tag:k.function(k.variableName),color:"#d8c37a"},{tag:k.operator,color:"#c9b8a5"},{tag:k.punctuation,color:"#8a8378"},{tag:k.variableName,color:"var(--code-text)"}]);function h(C){u==null||u.destroy(),d.value&&(u=new F({parent:d.value,state:le.create({doc:C,extensions:[Fe(),Re(),Ve(),De(),Ge(),Ke.of([...Ye,...Je]),le.readOnly.of(!0),F.editable.of(!1),F.lineWrapping,b,Xe(v),We()]})}))}async function _(){try{await navigator.clipboard.writeText(s.code)}catch{const C=document.createElement("textarea");C.value=s.code,document.body.appendChild(C),C.select(),document.execCommand("copy"),C.remove()}r.value=!0,window.clearTimeout(g),g=window.setTimeout(()=>{r.value=!1},1600)}return fe(()=>h(s.code)),ee(()=>s.code,C=>{h(C),c.value+=1}),ge(()=>{u==null||u.destroy(),window.clearTimeout(g)}),o({copy:_}),(C,L)=>(l(),x("div",jt,[e("div",Pt,[e("div",St,[L[0]||(L[0]=e("span",{class:"status-led","aria-hidden":"true"},null,-1)),e("span",Ot,f(t.file),1),e("span",qt,f(t.lang),1),e("span",zt,f(m.value)+" 行",1)]),e("button",{type:"button",class:q(["copy-btn",{copied:r.value}]),onClick:_},[r.value?(l(),M(p(Q),{key:0,size:13})):(l(),M(p($e),{key:1,size:13})),H(" "+f(r.value?"已复制":"复制"),1)],2)]),e("div",{ref_key:"host",ref:d,class:"cm-host"},null,512),(l(),x("div",{key:c.value,class:"scan-line","aria-hidden":"true"}))]))}}),Tt={class:"detail"},Lt={class:"detail-head"},At={class:"detail-title-row"},Ht={class:"detail-title"},Ut={key:0,class:"tag"},Bt={class:"detail-meta"},It={class:"meta-item"},Ft={class:"meta-item"},Rt={class:"meta-item"},Vt={class:"meta-item priority"},Dt={class:"detail-desc"},Gt=T({__name:"TemplateDetail",props:{template:{},variant:{}},setup(t){const o=t,s=P(()=>{var c;return((c=o.variant)==null?void 0:c.code)??o.template.code}),d=P(()=>{var c;return((c=o.variant)==null?void 0:c.file)??o.template.file}),r=P(()=>{var c;return((c=o.variant)==null?void 0:c.lang)??o.template.lang});return(c,m)=>(l(),x("div",Tt,[e("div",Lt,[e("div",At,[e("h2",Ht,f(t.template.name),1),t.variant?(l(),x("span",Ut,f(t.variant.name),1)):O("",!0),(l(!0),x(z,null,E(t.template.tags,u=>(l(),x("span",{key:u,class:"tag"},f(u),1))),128))]),e("div",Bt,[e("span",It,[m[0]||(m[0]=e("b",null,"分类",-1)),H(f(p(he)(t.template.cat).name),1)]),e("span",Ft,[m[1]||(m[1]=e("b",null,"来源",-1)),H(f(t.template.src),1)]),e("span",Rt,[m[2]||(m[2]=e("b",null,"更新于",-1)),H(f(t.template.updated),1)]),e("span",Vt,[m[3]||(m[3]=e("b",null,"优先级",-1)),H(f(t.template.priority??0),1)])])]),w(Et,{code:s.value,file:d.value,lang:r.value},null,8,["code","file","lang"]),e("div",Dt,f(t.template.desc),1)]))}}),Kt={class:"lib-page"},Yt={class:"lib-content"},Jt={class:"tpl-panel"},Xt={class:"tpl-panel-head"},Wt={key:0,class:"cat-dropdown",role:"menu","aria-label":"按分类筛选"},Zt=["aria-checked","onClick"],Qt={class:"tpl-tools"},ea={class:"toolbar-meta"},ta={class:"tpl-list"},aa=["onClick"],na={class:"tpl-idx"},sa={class:"tpl-cell"},ia={class:"tpl-name"},oa={class:"tpl-name-text"},la={class:"tpl-meta"},ra={key:0,class:"tpl-variants"},ca=["onClick"],da={class:"variant-name"},ua={class:"variant-lang"},pa={key:1,class:"detail empty-detail"},va=T({__name:"TemplateLibrary",props:{templates:{}},setup(t){const o=t,s=$(""),d=$("all"),r=$("updated"),c=$(null),m=$(!1),u=$({}),g=$(null),b=[{label:"按更新时间",value:"updated"},{label:"按名称",value:"name"},{label:"按优先级",value:"priority"}],v=P(()=>{const n=s.value.trim().toLowerCase();return[...o.templates.filter(a=>{const y=d.value==="all"||a.cat===d.value,N=[a.name,a.desc,a.code,a.src,a.tags.join(" ")].join(" ").toLowerCase();return y&&(!n||N.includes(n))})].sort((a,y)=>{if(r.value==="name")return a.name.localeCompare(y.name,"zh-Hans-CN");if(r.value==="priority"){const N=(y.priority??0)-(a.priority??0);return N!==0?N:a.updated<y.updated?1:-1}return a.updated<y.updated?1:-1})}),h=P(()=>v.value.find(n=>n.id===c.value)??v.value[0]??null),_=P(()=>{var i;const n=h.value;return(i=n==null?void 0:n.variants)!=null&&i.length?n.variants.find(a=>{var y;return a.id===((y=g.value)==null?void 0:y.id)})??n.variants[0]:null}),C=P(()=>{var n;return((n=_.value)==null?void 0:n.id)??null});ee(h,n=>{var i;(i=n==null?void 0:n.variants)!=null&&i.length&&u.value[n.id]===void 0&&(u.value[n.id]=!0)},{immediate:!0});function L(n){var a;c.value=n.id;for(const y of Object.keys(u.value))Number(y)!==n.id&&(u.value[Number(y)]=!1);if(!((a=n.variants)!=null&&a.length)){g.value=null;return}const i=!u.value[n.id];u.value[n.id]=i,i?g.value=n.variants[0]:g.value=null}function U(n,i){c.value=n.id;for(const a of Object.keys(u.value))Number(a)!==n.id&&(u.value[Number(a)]=!1);u.value[n.id]=!0,g.value=i}function K(n){d.value=n,m.value=!1}function B(){s.value="",d.value="all"}return(n,i)=>(l(),x("div",Kt,[e("div",Yt,[e("div",Jt,[e("div",Xt,[e("div",{class:"search-wrap",onMouseover:i[1]||(i[1]=a=>m.value=!0),onMouseleave:i[2]||(i[2]=a=>m.value=!1)},[w(p(Oe),{value:s.value,"onUpdate:value":i[0]||(i[0]=a=>s.value=a),class:"search-input",clearable:"",placeholder:"搜索模板、说明或代码…"},{prefix:j(()=>[w(p(Ce),{size:15})]),_:1},8,["value"]),w(W,{name:"cat-drop"},{default:j(()=>[m.value?(l(),x("div",Wt,[(l(!0),x(z,null,E(p(V),a=>(l(),x("button",{key:a.id,type:"button",class:q(["cat-option",{active:d.value===a.id}]),role:"menuitem","aria-checked":d.value===a.id,onClick:y=>K(a.id)},[e("span",{class:"cat-option-dot",style:X(a.hue?{background:`hsl(${a.hue} 60% 50%)`}:{background:"var(--accent)"})},null,4),e("span",null,f(a.name),1),d.value===a.id?(l(),M(p(Q),{key:0,size:14,class:"cat-check"})):O("",!0)],10,Zt))),128))])):O("",!0)]),_:1})],32),e("div",Qt,[w(p(qe),{value:r.value,"onUpdate:value":i[3]||(i[3]=a=>r.value=a),class:"sort-select",size:"small",options:b},null,8,["value"]),e("span",ea,f(v.value.length)+" / "+f(t.templates.length)+" 个模板",1)])]),e("div",ta,[w(Ne,{name:"tpl-list",tag:"div",class:"tpl-list-inner"},{default:j(()=>[(l(!0),x(z,null,E(v.value,(a,y)=>{var N,I,te;return l(),x("div",{key:a.id,class:q(["tpl-item",{open:u.value[a.id]}])},[e("button",{type:"button",class:q(["tpl-row",{active:a.id===((N=h.value)==null?void 0:N.id)}]),onClick:A=>L(a)},[e("span",na,f(String(y+1).padStart(2,"0")),1),e("span",sa,[e("span",ia,[e("span",{class:"cat-dot",style:X({background:`hsl(${p(Mt)(a.cat)} 55% 50%)`})},null,4),e("span",oa,f(a.name),1)]),e("span",la,f(a.updated),1)]),(I=a.variants)!=null&&I.length?(l(),M(p(me),{key:0,class:"tpl-chev",size:14})):O("",!0)],10,aa),(te=a.variants)!=null&&te.length?(l(),x("div",ra,[(l(!0),x(z,null,E(a.variants,A=>{var ae;return l(),x("button",{key:A.id,type:"button",class:q(["tpl-variant",{active:C.value===A.id&&a.id===((ae=h.value)==null?void 0:ae.id)}]),onClick:wa=>U(a,A)},[e("span",da,f(A.name),1),e("span",ua,f(A.lang),1)],10,ca)}),128))])):O("",!0)],2)}),128))]),_:1}),v.value.length?O("",!0):(l(),M(p(ze),{key:0,class:"empty-panel",description:"没有匹配的模板"},{extra:j(()=>[w(p(Ee),{size:"small",quaternary:"",onClick:B},{default:j(()=>[...i[4]||(i[4]=[H("清除筛选",-1)])]),_:1})]),_:1}))])]),w(W,{name:"detail-swap",mode:"out-in"},{default:j(()=>[h.value?(l(),M(Gt,{key:h.value.id,template:h.value,variant:_.value},null,8,["template","variant"])):(l(),x("div",pa,[w(p(Me),{size:32}),i[5]||(i[5]=e("span",null,"未选择模板",-1))]))]),_:1})])]))}});function G(t,o){try{const s=localStorage.getItem(t);return s===null?o:JSON.parse(s)}catch{return o}}function Z(t,o){try{localStorage.setItem(t,JSON.stringify(o))}catch{}}const ce="xc-theme-mode",de="xc-hue",Y=["light","dark","system"],ma={light:"亮色",dark:"暗色",system:"跟随系统"},J=window.matchMedia("(prefers-color-scheme: dark)");function fa(){const t=$(G(ce,"system")),o=$(G(de,160)),s=$(t.value==="dark"||t.value==="system"&&J.matches),d=P(()=>ma[t.value]),r=P(()=>t.value==="light"?"sun":t.value==="dark"?"moon":"monitor");function c(){s.value=t.value==="dark"||t.value==="system"&&J.matches}je(()=>{c(),document.documentElement.dataset.theme=s.value?"dark":"light",document.documentElement.style.setProperty("--hue",String(o.value)),Z(ce,t.value),Z(de,o.value)});function m(){const b=Y.indexOf(t.value);t.value=Y[(b+1)%Y.length]}function u(b){t.value=b}function g(b){o.value=Math.round(Math.min(360,Math.max(0,b)))}return J.addEventListener("change",()=>{t.value==="system"&&c()}),{mode:t,hue:o,isDark:s,modeLabel:d,modeIcon:r,cycleMode:m,setMode:u,setHue:g}}const S=[{id:1,name:"线段树（懒标记）",cat:"ds",lang:"cpp",file:"segtree_lazy.cpp",cplx:"区间修改/查询 O(log n)",tags:["区间加","区间和"],src:"洛谷 P3372",updated:"2026-07-28",priority:5,desc:"支持区间加、区间求和。下标从 1 开始，build 前读入原数组 a[]。注意 pushdown 时机，long long 必开。",lastUsedAt:"2026-07-30",code:`#include <bits/stdc++.h>
using namespace std;
typedef long long ll;
const int N = 1e5 + 10;

ll a[N], tr[N << 2], lz[N << 2];

void pushup(int p) { tr[p] = tr[p << 1] + tr[p << 1 | 1]; }

void pushdown(int p, int l, int r) {
    if (!lz[p]) return;
    int mid = (l + r) >> 1;
    lz[p << 1] += lz[p]; lz[p << 1 | 1] += lz[p];
    tr[p << 1] += lz[p] * (mid - l + 1);
    tr[p << 1 | 1] += lz[p] * (r - mid);
    lz[p] = 0;
}

void build(int p, int l, int r) {
    if (l == r) { tr[p] = a[l]; return; }
    int mid = (l + r) >> 1;
    build(p << 1, l, mid);
    build(p << 1 | 1, mid + 1, r);
    pushup(p);
}

void update(int p, int l, int r, int ql, int qr, ll v) {
    if (ql <= l && r <= qr) {
        tr[p] += v * (r - l + 1);
        lz[p] += v;
        return;
    }
    pushdown(p, l, r);
    int mid = (l + r) >> 1;
    if (ql <= mid) update(p << 1, l, mid, ql, qr, v);
    if (qr > mid) update(p << 1 | 1, mid + 1, r, ql, qr, v);
    pushup(p);
}

ll query(int p, int l, int r, int ql, int qr) {
    if (ql <= l && r <= qr) return tr[p];
    pushdown(p, l, r);
    int mid = (l + r) >> 1;
    ll res = 0;
    if (ql <= mid) res += query(p << 1, l, mid, ql, qr);
    if (qr > mid) res += query(p << 1 | 1, mid + 1, r, ql, qr);
    return res;
}`},{id:2,name:"树状数组",cat:"ds",lang:"cpp",file:"bit.cpp",cplx:"单点改/前缀和 O(log n)",tags:["前缀和","逆序对"],src:"洛谷 P3374",updated:"2026-07-20",priority:4,desc:"经典 BIT，下标从 1 开始。求逆序对时先离散化。",lastUsedAt:"2026-07-22",code:`#include <bits/stdc++.h>
using namespace std;
const int N = 5e5 + 10;

int n, tr[N];

inline int lowbit(int x) { return x & -x; }

void add(int x, int v) {
    for (; x <= n; x += lowbit(x)) tr[x] += v;
}

int query(int x) {
    int res = 0;
    for (; x; x -= lowbit(x)) res += tr[x];
    return res;
}`},{id:3,name:"并查集（路径压缩 + 按秩合并）",cat:"ds",lang:"cpp",file:"dsu.cpp",cplx:"近似 O(1)",tags:["连通性"],src:"洛谷 P3367",updated:"2026-06-30",priority:5,desc:"两个优化都写上，复杂度才有保证。可扩展为带权并查集。",lastUsedAt:"2026-07-05",code:`#include <bits/stdc++.h>
using namespace std;
const int N = 1e5 + 10;

int fa[N], rnk[N];

void init(int n) {
    for (int i = 1; i <= n; i++) fa[i] = i, rnk[i] = 0;
}

int find(int x) {
    return fa[x] == x ? x : fa[x] = find(fa[x]);
}

void merge(int x, int y) {
    x = find(x), y = find(y);
    if (x == y) return;
    if (rnk[x] < rnk[y]) swap(x, y);
    fa[y] = x;
    if (rnk[x] == rnk[y]) rnk[x]++;
}`},{id:4,name:"Dijkstra（堆优化）",cat:"graph",lang:"cpp",file:"dijkstra.cpp",cplx:"O((n + m) log m)",tags:["最短路","非负权"],src:"洛谷 P4779",updated:"2026-07-15",priority:4,desc:"非负边权最短路。注意链式前向星或 vector 邻接表均可，dis 初始化 INF。",lastUsedAt:"2026-07-29",code:`#include <bits/stdc++.h>
using namespace std;
typedef long long ll;
typedef pair<ll, int> pli;
const int N = 1e5 + 10;
const ll INF = 0x3f3f3f3f3f3f3f3f;

vector<pli> g[N]; // (边权, 终点)
ll dis[N];
bool vis[N];

void dijkstra(int s) {
    memset(dis, 0x3f, sizeof dis);
    priority_queue<pli, vector<pli>, greater<pli>> q;
    dis[s] = 0;
    q.push({0, s});
    while (!q.empty()) {
        auto [d, u] = q.top(); q.pop();
        if (vis[u]) continue;
        vis[u] = true;
        for (auto [w, v] : g[u]) {
            if (dis[v] > dis[u] + w) {
                dis[v] = dis[u] + w;
                q.push({dis[v], v});
            }
        }
    }
}`},{id:5,name:"Tarjan 强连通分量",cat:"graph",lang:"cpp",file:"tarjan_scc.cpp",cplx:"O(n + m)",tags:["SCC","缩点"],src:"洛谷 B3609",updated:"2026-05-12",priority:3,desc:"缩点后得到 DAG。注意 instk 的维护，回溯时 low[u] = min(low[u], dfn[v]) 只在 v 在栈中时。",lastUsedAt:"2026-06-02",code:`#include <bits/stdc++.h>
using namespace std;
const int N = 1e5 + 10;

vector<int> g[N];
int dfn[N], low[N], timer_;
int stk[N], top_, scc[N], cnt;
bool instk[N];

void tarjan(int u) {
    dfn[u] = low[u] = ++timer_;
    stk[++top_] = u; instk[u] = true;
    for (int v : g[u]) {
        if (!dfn[v]) {
            tarjan(v);
            low[u] = min(low[u], low[v]);
        } else if (instk[v]) {
            low[u] = min(low[u], dfn[v]);
        }
    }
    if (dfn[u] == low[u]) {
        cnt++;
        int x;
        do {
            x = stk[top_--];
            instk[x] = false;
            scc[x] = cnt;
        } while (x != u);
    }
}`},{id:6,name:"KMP",cat:"string",lang:"cpp",file:"kmp.cpp",cplx:"O(n + m)",tags:["模式匹配"],src:"洛谷 P3375",updated:"2026-04-18",priority:2,desc:"next 数组即 border 长度。下标从 1 开始更不容易写错。",lastUsedAt:"2026-07-11",code:`#include <bits/stdc++.h>
using namespace std;
const int N = 1e6 + 10;

char s[N], p[N];
int nxt[N];

void get_next(char *p, int m) {
    nxt[1] = 0;
    for (int i = 2, j = 0; i <= m; i++) {
        while (j && p[i] != p[j + 1]) j = nxt[j];
        if (p[i] == p[j + 1]) j++;
        nxt[i] = j;
    }
}

void kmp(char *s, int n, char *p, int m) {
    for (int i = 1, j = 0; i <= n; i++) {
        while (j && s[i] != p[j + 1]) j = nxt[j];
        if (s[i] == p[j + 1]) j++;
        if (j == m) {
            printf("%d\\n", i - m + 1); // 匹配起点（1-indexed）
            j = nxt[j];
        }
    }
}`},{id:7,name:"快速幂",cat:"math",lang:"cpp",file:"qpow.cpp",cplx:"O(log n)",tags:["取模"],src:"洛谷 P1226",updated:"2026-03-08",priority:4,desc:"底数先取模。乘法溢出时用 __int128 或慢速乘。",lastUsedAt:"2026-07-31",code:`#include <bits/stdc++.h>
using namespace std;
typedef long long ll;

ll qpow(ll a, ll b, ll mod) {
    ll res = 1 % mod;
    a %= mod;
    while (b) {
        if (b & 1) res = res * a % mod;
        a = a * a % mod;
        b >>= 1;
    }
    return res;
}`},{id:8,name:"线性筛（欧拉筛）",cat:"math",lang:"cpp",file:"euler_sieve.cpp",cplx:"O(n)",tags:["素数","积性函数"],src:"洛谷 P3383",updated:"2026-06-01",priority:3,desc:"每个合数只被最小质因子筛掉一次。可顺手筛 phi / mu。",lastUsedAt:"2026-06-18",code:`#include <bits/stdc++.h>
using namespace std;
const int N = 1e7 + 10;

int prime[N], cnt;
bool vis[N];

void sieve(int n) {
    for (int i = 2; i <= n; i++) {
        if (!vis[i]) prime[++cnt] = i;
        for (int j = 1; j <= cnt && 1LL * i * prime[j] <= n; j++) {
            vis[i * prime[j]] = true;
            if (i % prime[j] == 0) break;
        }
    }
}`},{id:9,name:"0-1 背包",cat:"dp",lang:"cpp",file:"knapsack01.cpp",cplx:"O(n · V)",tags:["背包"],src:"洛谷 P1048",updated:"2026-02-14",priority:4,desc:"一维滚动数组时体积必须倒序枚举，完全背包则正序。",lastUsedAt:"2026-05-09",code:`#include <bits/stdc++.h>
using namespace std;
const int V = 1e4 + 10;

int f[V]; // f[j] = 体积 j 内的最大价值

// w: 体积, v: 价值, m: 背包容量
void knapsack01(int w, int v, int m) {
    for (int j = m; j >= w; j--)
        f[j] = max(f[j], f[j - w] + v);
}`},{id:10,name:"快读 / 快写",cat:"misc",lang:"cpp",file:"fastio.cpp",cplx:"比 cin 快约 10 倍",tags:["卡常"],src:"通用",updated:"2026-01-20",priority:3,desc:"数据量 1e6 以上建议换掉 cin/cout，或至少 sync_with_stdio(false)。",lastUsedAt:"2026-07-27",code:`#include <bits/stdc++.h>
using namespace std;

inline int read() {
    int x = 0, f = 1;
    char c = getchar();
    while (c < '0' || c > '9') {
        if (c == '-') f = -1;
        c = getchar();
    }
    while (c >= '0' && c <= '9') {
        x = x * 10 + c - '0';
        c = getchar();
    }
    return x * f;
}

inline void write(int x) {
    if (x < 0) putchar('-'), x = -x;
    if (x > 9) write(x / 10);
    putchar(x % 10 + '0');
}`},{id:11,name:"字符串哈希（双模）",cat:"string",lang:"cpp",file:"str_hash.cpp",cplx:"预处理 O(n)，查询 O(1)",tags:["哈希","回文"],src:"洛谷 P3370",updated:"2026-05-27",priority:4,desc:"双模基本不会撞。base 取 131 或 13331，模数用两个大质数。",lastUsedAt:"2026-06-25",code:`#include <bits/stdc++.h>
using namespace std;
typedef long long ll;
const int N = 1e6 + 10;
const ll B = 131, M1 = 1e9 + 7, M2 = 998244353;

ll h1[N], h2[N], p1[N], p2[N];

void init(char *s, int n) {
    p1[0] = p2[0] = 1;
    for (int i = 1; i <= n; i++) {
        p1[i] = p1[i - 1] * B % M1;
        p2[i] = p2[i - 1] * B % M2;
        h1[i] = (h1[i - 1] * B + s[i]) % M1;
        h2[i] = (h2[i - 1] * B + s[i]) % M2;
    }
}

pair<ll, ll> get(int l, int r) {
    ll x = (h1[r] - h1[l - 1] * p1[r - l + 1] % M1 + M1) % M1;
    ll y = (h2[r] - h2[l - 1] * p2[r - l + 1] % M2 + M2) % M2;
    return {x, y};
}`},{id:12,name:"离散化",cat:"misc",lang:"cpp",file:"discretize.cpp",cplx:"O(n log n)",tags:["预处理"],src:"通用",updated:"2026-03-30",priority:3,desc:"排序 + 去重 + lower_bound，返回 1-indexed 排名方便套树状数组。",lastUsedAt:"2026-04-02",code:`#include <bits/stdc++.h>
using namespace std;

vector<int> vals; // 先 push 所有可能出现的值

void build() {
    sort(vals.begin(), vals.end());
    vals.erase(unique(vals.begin(), vals.end()), vals.end());
}

int get(int x) { // 返回 1-indexed
    return lower_bound(vals.begin(), vals.end(), x) - vals.begin() + 1;
}`}];S[0].variants=[{id:"segtree-std",name:"标准版",lang:"cpp",file:"segtree_lazy.cpp",code:S[0].code},{id:"segtree-debug",name:"调试版",lang:"cpp",file:"segtree_lazy_debug.cpp",code:S[0].code}];S[2].variants=[{id:"dsu-rank",name:"路径压缩版",lang:"cpp",file:"dsu.cpp",code:S[2].code},{id:"dsu-weight",name:"带权版",lang:"cpp",file:"dsu_weight.cpp",code:S[2].code}];S[3].variants=[{id:"dijkstra-vector",name:"vector 邻接表",lang:"cpp",file:"dijkstra.cpp",code:S[3].code},{id:"dijkstra-chain",name:"链式前向星",lang:"cpp",file:"dijkstra_chain.cpp",code:S[3].code}];const be="xc-templates-v3",ga="xc-templates-v2";function ue(t){return t.map(o=>{if(typeof o.priority=="number")return o;const s=S.find(d=>d.id===o.id);return{...o,priority:(s==null?void 0:s.priority)??0}})}function ha(){const t=G(be,null);if(t)return ue(t);const o=G(ga,null);return o?ue(o):S}function ba(){const t=$(ha());ee(t,s=>{Z(be,s)},{deep:!0});function o(s){const d=t.value.reduce((c,m)=>Math.max(c,m.id),0)+1,r=s.name.toLowerCase().replace(/[^\w\u4e00-\u9fa5]+/g,"_").replace(/^_+|_+$/g,"")||`template_${d}`;t.value.unshift({id:d,name:s.name,cat:s.cat,lang:s.lang,file:`${r}.${s.lang==="py"?"py":s.lang==="java"?"java":"cpp"}`,cplx:s.cplx||"未标注",tags:[],src:s.src||"本地新建",updated:new Date().toISOString().slice(0,10),priority:s.priority??0,desc:s.desc||"暂无说明",code:s.code,lastUsedAt:null})}return{templates:t,addTemplate:o}}const ya={class:"app-shell"},xa={class:"main-pane"},_a={class:"page-stage"},ka=T({__name:"App",setup(t){const{mode:o,hue:s,isDark:d,modeIcon:r,modeLabel:c,cycleMode:m,setMode:u,setHue:g}=fa(),{templates:b}=ba(),v=$("lib"),h=$({templates:!0}),_=P(()=>v.value==="lib"?re.books:re[v.value]),C=P(()=>{var a;const n=R.find(y=>{var N;return y.page===v.value||((N=y.children)==null?void 0:N.some(I=>I.page===v.value))});if(!n)return{group:"",sub:""};if(n.page===v.value)return{group:n.label,sub:""};const i=(a=n.children)==null?void 0:a.find(y=>y.page===v.value);return{group:n.label,sub:(i==null?void 0:i.label)??""}}),L=P(()=>{const n=!d.value,i=`hsl(${s.value}, 68%, ${n?48:24}%)`,a=`hsl(${s.value}, 72%, ${n?36:32}%)`,y=`hsl(${s.value}, 70%, ${n?40:28}%)`,N=`hsla(${s.value}, 60%, 40%, 0.16)`;return{common:{primaryColor:i,primaryColorHover:a,primaryColorPressed:y,primaryColorSuppl:a,borderRadius:"8px",borderRadiusSmall:"6px",fontFamily:"var(--font-ui)",fontFamilyMono:"var(--font-mono)",textColorBase:"var(--text)",bodyColor:"var(--bg)"},Button:{textColorPrimary:"var(--on-accent)",colorPrimary:i,colorHoverPrimary:a,colorPressedPrimary:y,colorFocusPrimary:a,borderPrimary:`1px solid ${i}`,borderHoverPrimary:`1px solid ${a}`,borderPressedPrimary:`1px solid ${y}`,borderRadiusMedium:"6px",borderRadiusSmall:"6px"},Input:{color:"var(--surface)",colorFocus:"var(--surface)",border:"1px solid var(--border)",borderHover:"1px solid var(--border-strong)",borderFocus:"1px solid var(--accent)",boxShadowFocus:`0 0 0 3px ${N}`,textColor:"var(--text)",placeholderColor:"var(--faint)",caretColor:"var(--accent)"},Select:{color:"var(--surface)",colorHover:"var(--surface)",colorActive:"var(--surface)",border:"1px solid var(--border)",borderHover:"1px solid var(--border-strong)",borderFocus:"1px solid var(--accent)",boxShadowFocus:`0 0 0 3px ${N}`,textColor:"var(--text)",placeholderColor:"var(--faint)"},Modal:{color:"var(--surface)",borderRadius:"12px"},Popover:{color:"var(--surface)",borderRadius:"8px",boxShadow:"var(--shadow-pop)",border:"1px solid var(--border)"},Slider:{fillColor:i,fillColorHover:i,railColor:"var(--border)",railColorHover:"var(--border-strong)",handleColor:"#ffffff",handleBoxShadow:"0 1px 4px rgb(0 0 0 / 0.35)"},Tooltip:{color:"var(--text)",textColor:"var(--bg)",borderRadius:"6px"},Message:{color:"var(--text)",textColor:"var(--bg)",borderRadius:"6px"}}});function U(n){v.value=n;const i=R.find(a=>{var y;return a.page===n||((y=a.children)==null?void 0:y.some(N=>N.page===n))});i&&(h.value[i.id]=!0)}function K(n){const i=R.find(a=>a.id===n);i&&(h.value[n]=!h.value[n],h.value[n]&&i.children&&!i.children.some(a=>a.page===v.value)&&(v.value=i.children[0].page))}function B(n){(n.ctrlKey||n.metaKey)&&n.key.toLowerCase()==="k"&&(n.preventDefault(),v.value!=="lib"&&U("lib"),requestAnimationFrame(()=>{var i;(i=document.querySelector(".search-input input"))==null||i.focus()}))}return fe(()=>document.addEventListener("keydown",B)),ge(()=>document.removeEventListener("keydown",B)),(n,i)=>(l(),M(p(Be),{theme:p(d)?p(He):p(Ue),"theme-overrides":L.value,locale:p(Ae),"date-locale":p(Le)},{default:j(()=>[w(p(Te),{placement:"bottom"},{default:j(()=>[e("div",ya,[w(lt,{"active-page":v.value,"open-groups":h.value,onNavigate:U,onToggle:K},null,8,["active-page","open-groups"]),e("main",xa,[w(_t,{"page-meta":C.value,mode:p(o),"mode-icon":p(r),"mode-label":p(c),hue:p(s),onCycleTheme:p(m),onSetMode:p(u),onSetHue:p(g)},null,8,["page-meta","mode","mode-icon","mode-label","hue","onCycleTheme","onSetMode","onSetHue"]),e("section",_a,[w(W,{name:"page-swap",mode:"out-in"},{default:j(()=>[v.value==="lib"?(l(),M(va,{key:0,templates:p(b)},null,8,["templates"])):(l(),M(Nt,{key:1,page:v.value,meta:_.value},null,8,["page","meta"]))]),_:1})])])])]),_:1})]),_:1},8,["theme","theme-overrides","locale","date-locale"]))}});Pe(ka).mount("#app");
