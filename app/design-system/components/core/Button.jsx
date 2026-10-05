import React from 'react';
const SIZES={sm:{height:36,padding:'0 16px',fontSize:15,gap:6},md:{height:44,padding:'0 20px',fontSize:17,gap:8},lg:{height:52,padding:'0 26px',fontSize:18,gap:10}};
const VARIANTS={
  primary:{bg:'var(--ink-1)',bgH:'var(--ink-2)',fg:'var(--paper-1)',bd:'var(--ink-1)'},
  accent:{bg:'var(--ochre-500)',bgH:'var(--ochre-300)',fg:'var(--ink-1)',bd:'var(--ochre-500)'},
  secondary:{bg:'transparent',bgH:'var(--paper-2)',fg:'var(--ink-1)',bd:'var(--ink-1)'},
  ghost:{bg:'transparent',bgH:'var(--paper-2)',fg:'var(--ink-1)',bd:'transparent'},
  danger:{bg:'var(--brick-600)',bgH:'var(--danger-hover)',fg:'var(--paper-0)',bd:'var(--brick-600)'}
};
export function Button({variant='primary',size='md',disabled=false,fullWidth=false,iconStart,iconEnd,children,style,...rest}){
  const [h,setH]=React.useState(false);const [p,setP]=React.useState(false);
  const v=VARIANTS[variant]||VARIANTS.primary,s=SIZES[size]||SIZES.md;
  return <button disabled={disabled} onMouseEnter={()=>setH(true)} onMouseLeave={()=>{setH(false);setP(false)}} onMouseDown={()=>setP(true)} onMouseUp={()=>setP(false)} {...rest} style={{display:'inline-flex',alignItems:'center',justifyContent:'center',gap:s.gap,height:s.height,padding:s.padding,width:fullWidth?'100%':undefined,
    font:'500 '+s.fontSize+'px/1 var(--font-ui)',color:v.fg,background:h&&!disabled?v.bgH:v.bg,border:'var(--stroke-pen) solid '+v.bd,borderRadius:'var(--radius-md)',
    cursor:disabled?'not-allowed':'pointer',opacity:disabled?.4:1,transform:p&&!disabled?'translateY(1px)':'none',transition:'background var(--dur-fast) var(--ease-out), transform var(--dur-fast)',whiteSpace:'nowrap',...style}}>
    {iconStart}{children}{iconEnd}</button>;
}
