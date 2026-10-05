import React from 'react';
export function Tabs({tabs=[],value,defaultValue,onChange}){
  const [v,setV]=React.useState(defaultValue??(tabs[0]&&(tabs[0].value??tabs[0])));const cur=value??v;
  return <div role="tablist" style={{display:'flex',gap:28,borderBottom:'var(--stroke-hair) solid var(--border-default)'}}>{tabs.map(t=>{const val=t.value??t,lab=t.label??t,on=val===cur;
    return <button key={val} role="tab" aria-selected={on} onClick={()=>{setV(val);onChange&&onChange(val);}} style={{all:'unset',cursor:'pointer',padding:'14px 0',marginBottom:-1,font:(on?'500':'400')+' 17px/1.2 var(--font-ui)',color:on?'var(--ink-1)':'var(--text-muted)',borderBottom:'var(--stroke-bold) solid '+(on?'var(--ink-1)':'transparent'),display:'inline-flex',alignItems:'center',gap:8,transition:'color var(--dur-fast)'}}>
      {lab}{t.count!=null&&<span style={{font:'500 13px/1 var(--font-ui)',padding:'3px 7px',borderRadius:'var(--radius-pill)',background:on?'var(--ochre-50)':'var(--paper-3)',color:on?'var(--ochre-700)':'var(--ink-3)'}}>{t.count}</span>}</button>;})}</div>;
}
