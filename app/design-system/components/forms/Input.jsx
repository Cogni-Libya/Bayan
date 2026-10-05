import React from 'react';
const Field=({label,hint,error,children,id})=><label htmlFor={id} style={{display:'grid',gap:6}}>{label&&<span style={{font:'var(--type-label)',color:'var(--ink-1)'}}>{label}</span>}{children}{(error||hint)&&<span style={{font:'var(--type-caption)',color:error?'var(--danger)':'var(--text-muted)'}}>{error||hint}</span>}</label>;
const fs=(f,error,disabled)=>({height:48,padding:'0 16px',boxSizing:'border-box',width:'100%',font:'400 17px/1 var(--font-ui)',color:'var(--ink-1)',background:disabled?'var(--paper-2)':'var(--surface-raised)',
  border:'var(--stroke-pen) solid '+(error?'var(--danger)':f?'var(--ink-1)':'var(--border-default)'),borderRadius:'var(--radius-md)',outline:'none',boxShadow:f?'var(--ring)':'none',transition:'border-color var(--dur-fast), box-shadow var(--dur-fast)',opacity:disabled?.6:1});
export function Input({label,hint,error,disabled,id,style,...rest}){
  const [f,setF]=React.useState(false);const iid=id||React.useId();
  return <Field label={label} hint={hint} error={error} id={iid}><input id={iid} disabled={disabled} onFocus={()=>setF(true)} onBlur={()=>setF(false)} {...rest} style={{...fs(f,error,disabled),...style}}/></Field>;
}
