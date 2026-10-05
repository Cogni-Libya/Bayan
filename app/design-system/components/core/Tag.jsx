import React from 'react';
export function Tag({selected=false,onRemove,onClick,children,style}){
  const [h,setH]=React.useState(false);
  return <span onClick={onClick} onMouseEnter={()=>setH(true)} onMouseLeave={()=>setH(false)} style={{display:'inline-flex',alignItems:'center',gap:6,height:36,padding:'0 16px',borderRadius:'var(--radius-pill)',
    border:'var(--stroke-hair) solid '+(selected?'var(--ink-1)':'var(--border-default)'),background:selected?'var(--ink-1)':(h&&onClick?'var(--paper-2)':'var(--surface-raised)'),
    color:selected?'var(--paper-1)':'var(--ink-1)',font:'400 16px/1 var(--font-ui)',cursor:onClick?'pointer':'default',transition:'background var(--dur-fast)',...style}}>
    {children}{onRemove&&<button aria-label="إزالة" onClick={e=>{e.stopPropagation();onRemove();}} style={{all:'unset',cursor:'pointer',fontSize:16,lineHeight:1,opacity:.6}}>×</button>}</span>;
}
