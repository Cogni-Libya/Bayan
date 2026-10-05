import React from 'react';
const DOT={neutral:'var(--paper-4)',accent:'var(--ochre-500)',success:'#9DB585',danger:'#D98A7E'};
export function Toast({tone='neutral',children,action,onClose}){
  return <div role="status" style={{display:'inline-flex',alignItems:'center',gap:14,minHeight:48,padding:'10px 12px 10px 16px',paddingInlineStart:16,boxSizing:'border-box',background:'var(--ink-1)',color:'var(--paper-1)',borderRadius:'var(--radius-md)',boxShadow:'var(--shadow-3)',font:'400 16px/1.5 var(--font-ui)',maxWidth:480}}>
    <span style={{width:8,height:8,borderRadius:'50%',background:DOT[tone]||DOT.neutral,flex:'none'}}/>
    <span style={{flex:1}}>{children}</span>
    {action&&<span style={{font:'500 16px/1 var(--font-ui)',color:'var(--ochre-300)',cursor:'pointer'}}>{action}</span>}
    {onClose&&<button aria-label="إغلاق" onClick={onClose} style={{all:'unset',cursor:'pointer',opacity:.6,fontSize:18,lineHeight:1,padding:'0 4px'}}>×</button>}</div>;
}
