import React from 'react';
export function Checkbox({checked,defaultChecked=false,onChange,label,disabled}){
  const [c,setC]=React.useState(defaultChecked);const on=checked??c;
  const t=()=>{if(disabled)return;setC(!on);onChange&&onChange(!on);};
  return <label style={{display:'inline-flex',alignItems:'center',gap:10,cursor:disabled?'not-allowed':'pointer',opacity:disabled?.45:1,font:'var(--type-body)'}}>
    <span role="checkbox" aria-checked={on} tabIndex={0} onClick={t} onKeyDown={e=>e.key===' '&&(e.preventDefault(),t())} style={{width:20,height:20,boxSizing:'border-box',borderRadius:'var(--radius-xs)',border:'var(--stroke-pen) solid var(--ink-1)',background:on?'var(--ink-1)':'var(--surface-raised)',display:'grid',placeItems:'center',transition:'background var(--dur-fast)'}}>
      {on&&<span style={{width:5,height:10,borderRight:'2px solid var(--paper-1)',borderBottom:'2px solid var(--paper-1)',transform:'translateY(-1px) rotate(45deg)'}}/>}</span>
    {label&&<span onClick={t}>{label}</span>}</label>;
}
