import React from 'react';
export function Radio({name,options=[],value,defaultValue,onChange,direction='column'}){
  const [v,setV]=React.useState(defaultValue??(options[0]&&(options[0].value??options[0])));const cur=value??v;
  return <div role="radiogroup" style={{display:'flex',flexDirection:direction,gap:direction==='row'?20:12}}>{options.map(o=>{const val=o.value??o,lab=o.label??o,on=cur===val;
    return <label key={val} style={{display:'inline-flex',alignItems:'center',gap:10,cursor:'pointer',font:'var(--type-body)'}} onClick={()=>{setV(val);onChange&&onChange(val);}}>
      <span role="radio" aria-checked={on} style={{width:20,height:20,boxSizing:'border-box',borderRadius:'50%',border:'var(--stroke-pen) solid var(--ink-1)',display:'grid',placeItems:'center',background:'var(--surface-raised)'}}>
        <span style={{width:10,height:10,borderRadius:'50%',background:'var(--ochre-500)',transform:on?'scale(1)':'scale(0)',transition:'transform var(--dur-base) var(--ease-out)'}}/></span>{lab}</label>;})}</div>;
}
