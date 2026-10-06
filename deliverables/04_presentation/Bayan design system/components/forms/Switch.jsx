import React from 'react';
export function Switch({checked,defaultChecked=false,onChange,label,disabled}){
  const [c,setC]=React.useState(defaultChecked);const on=checked??c;
  const t=()=>{if(disabled)return;setC(!on);onChange&&onChange(!on);};
  return <label style={{display:'inline-flex',alignItems:'center',gap:12,cursor:disabled?'not-allowed':'pointer',opacity:disabled?.45:1,font:'var(--type-body)'}} onClick={t}>
    <span role="switch" aria-checked={on} style={{width:40,height:24,borderRadius:'var(--radius-pill)',background:on?'var(--ink-1)':'var(--paper-4)',position:'relative',transition:'background var(--dur-base)',flex:'none'}}>
      <span style={{position:'absolute',top:3,insetInlineStart:on?19:3,width:18,height:18,borderRadius:'50%',background:on?'var(--ochre-500)':'var(--paper-0)',boxShadow:'var(--shadow-1)',transition:'inset-inline-start var(--dur-base) var(--ease-page), background var(--dur-base)'}}/></span>
    {label&&<span>{label}</span>}</label>;
}
