import React from 'react';
const T={neutral:['var(--paper-3)','var(--ink-2)'],accent:['var(--ochre-50)','var(--ochre-700)'],success:['var(--success-soft)','var(--success)'],danger:['var(--danger-soft)','var(--danger)'],info:['var(--info-soft)','var(--info)'],ink:['var(--ink-1)','var(--paper-1)']};
export function Badge({tone='neutral',dot=false,children,style}){
  const [bg,fg]=T[tone]||T.neutral;
  return <span style={{display:'inline-flex',alignItems:'center',gap:6,height:26,padding:'0 11px',borderRadius:'var(--radius-pill)',background:bg,color:fg,font:'500 14px/1 var(--font-ui)',whiteSpace:'nowrap',...style}}>
    {dot&&<span style={{width:6,height:6,borderRadius:'50%',background:'currentColor'}}/>}{children}</span>;
}
