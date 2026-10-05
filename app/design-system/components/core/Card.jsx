import React from 'react';
export function Card({variant='outlined',padding='md',interactive=false,children,style,...rest}){
  const [h,setH]=React.useState(false);
  const pad={none:0,sm:'var(--space-4)',md:'var(--space-5)',lg:'var(--space-6)'}[padding];
  const base={outlined:{background:'var(--surface-raised)',border:'var(--stroke-hair) solid var(--border-default)',boxShadow:'none'},
    elevated:{background:'var(--surface-raised)',border:'var(--stroke-hair) solid var(--border-subtle)',boxShadow:'var(--shadow-2)'},
    sunken:{background:'var(--surface-sunken)',border:'var(--stroke-hair) solid transparent',boxShadow:'none'},
    inverse:{background:'var(--surface-inverse)',color:'var(--text-inverse)',border:'none',boxShadow:'none'}}[variant];
  return <div onMouseEnter={()=>setH(true)} onMouseLeave={()=>setH(false)} {...rest} style={{borderRadius:'var(--radius-lg)',padding:pad,...base,
    ...(interactive&&h?{borderColor:'var(--ink-1)',transform:'translateY(-2px)',cursor:'pointer'}:{}),transition:'transform var(--dur-base) var(--ease-page), border-color var(--dur-base)',...style}}>{children}</div>;
}
