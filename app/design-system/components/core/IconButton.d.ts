import * as React from 'react';
/** Circular icon-only button. Always pass `label` for accessibility. */
export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'ghost' | 'secondary' | 'primary';
  size?: 'sm' | 'md' | 'lg';
  label: string;
  children: React.ReactNode;
}
export declare function IconButton(props: IconButtonProps): JSX.Element;
