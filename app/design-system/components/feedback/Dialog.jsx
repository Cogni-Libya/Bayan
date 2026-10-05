import React from 'react';
export function Dialog({open=true,title,children,actions,onClose,inline=false,width=440}){
  if(!open)return null;
  const box=<div role="dialog" aria-modal="true" style={{width,maxWidth:'calc(100vw - 32px)',boxSizing:'border-box',background:'var(--surface-raised)',borderRadius:'var(--radius-xl)',boxShadow:'var(--shadow-3)',padding:'var(--space-6)',display:'grid',gap:'var(--space-4)'}}>
    {title&&<h3 style={{margin:0,font:'var(--type-h4)',color:'var(--ink-1)'}}>{title}</h3>}
    <div style={{font:'var(--type-body)',color:'var(--ink-2)'}}>{children}</div>
    {actions&&<div style={{display:'flex',gap:'var(--space-2)',justifyContent:'flex-end',marginTop:'var(--space-2)'}}>{actions}</div>}</div>;
  if(inline)return box;
  return <div onClick={e=>e.target===e.currentTarget&&onClose&&onClose()} style={{position:'fixed',inset:0,background:'var(--scrim)',display:'grid',placeItems:'center',zIndex:1000}}>{box}</div>;
}
