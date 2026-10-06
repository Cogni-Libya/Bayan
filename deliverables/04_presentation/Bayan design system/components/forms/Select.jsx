import React from 'react';
const Field=({label,hint,error,children,id})=><label htmlFor={id} style={{display:'grid',gap:6}}>{label&&<span style={{font:'var(--type-label)',color:'var(--ink-1)'}}>{label}</span>}{children}{(error||hint)&&<span style={{font:'var(--type-caption)',color:error?'var(--danger)':'var(--text-muted)'}}>{error||hint}</span>}</label>;
const fs=(f,error,disabled)=>({height:48,padding:'0 16px',boxSizing:'border-box',width:'100%',font:'400 17px/1 var(--font-ui)',color:'var(--ink-1)',background:disabled?'var(--paper-2)':'var(--surface-raised)',
  border:'var(--stroke-pen) solid '+(error?'var(--danger)':f?'var(--ink-1)':'var(--border-default)'),borderRadius:'var(--radius-md)',outline:'none',boxShadow:f?'var(--ring)':'none',transition:'border-color var(--dur-fast), box-shadow var(--dur-fast)',opacity:disabled?.6:1});
export function Select({label,hint,error,disabled,options=[],id,style,...rest}){
  const [f,setF]=React.useState(false);const iid=id||React.useId();
  return <Field label={label} hint={hint} error={error} id={iid}><div style={{position:'relative'}}>
    <select id={iid} disabled={disabled} onFocus={()=>setF(true)} onBlur={()=>setF(false)} {...rest} style={{...fs(f,error,disabled),appearance:'none',paddingInlineEnd:36,cursor:'pointer',...style}}>
      {options.map(o=>typeof o==='string'?<option key={o} value={o}>{o}</option>:<option key={o.value} value={o.value}>{o.label}</option>)}</select>
    <span aria-hidden style={{position:'absolute',insetInlineEnd:14,top:'50%',width:7,height:7,borderInlineEnd:'1.5px solid var(--ink-1)',borderBottom:'1.5px solid var(--ink-1)',transform:'translateY(-70%) rotate(45deg)',pointerEvents:'none'}}/></div></Field>;
}
