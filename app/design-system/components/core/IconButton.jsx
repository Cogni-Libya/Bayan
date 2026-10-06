import React from 'react';
export function IconButton({variant='ghost',size='md',label,disabled=false,children,style,...rest}){
  const [h,setH]=React.useState(false);const [p,setP]=React.useState(false);
  const d={sm:36,md:44,lg:52}[size]||44;
  const V={ghost:['transparent','var(--paper-2)','transparent'],secondary:['transparent','var(--paper-2)','var(--ink-1)'],primary:['var(--ink-1)','var(--ink-2)','var(--ink-1)']}[variant]||[];
  return <button aria-label={label} title={label} disabled={disabled} onMouseEnter={()=>setH(true)} onMouseLeave={()=>{setH(false);setP(false)}} onMouseDown={()=>setP(true)} onMouseUp={()=>setP(false)} {...rest} style={{width:d,height:d,display:'inline-grid',placeItems:'center',padding:0,
    background:h&&!disabled?V[1]:V[0],border:'var(--stroke-pen) solid '+V[2],borderRadius:'var(--radius-pill)',color:variant==='primary'?'var(--paper-1)':'var(--ink-1)',
    cursor:disabled?'not-allowed':'pointer',opacity:disabled?.4:1,transform:p?'scale(.94)':'none',transition:'background var(--dur-fast), transform var(--dur-fast)',...style}}>{children}</button>;
}
