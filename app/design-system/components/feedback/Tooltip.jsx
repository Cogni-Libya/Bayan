import React from 'react';
export function Tooltip({content,side='top',open,children}){
  const [h,setH]=React.useState(false);const show=open??h;
  const pos={top:{bottom:'calc(100% + 8px)',left:'50%',transform:'translateX(-50%)'},bottom:{top:'calc(100% + 8px)',left:'50%',transform:'translateX(-50%)'}}[side];
  return <span style={{position:'relative',display:'inline-flex'}} onMouseEnter={()=>setH(true)} onMouseLeave={()=>setH(false)}>{children}
    {show&&<span role="tooltip" style={{position:'absolute',...pos,background:'var(--ink-1)',color:'var(--paper-1)',font:'400 14px/1.4 var(--font-ui)',padding:'6px 10px',borderRadius:'var(--radius-sm)',whiteSpace:'nowrap',pointerEvents:'none',zIndex:10}}>{content}</span>}</span>;
}
