import * as React from 'react';
/**
 * Bayan button. Ink primary, ochre accent (max one per view), outlined secondary, ghost, danger.
 * @startingPoint section="Core" subtitle="Buttons in all variants and sizes" viewport="700x260"
 */
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'accent' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
  iconStart?: React.ReactNode;
  iconEnd?: React.ReactNode;
  children?: React.ReactNode;
}
export declare function Button(props: ButtonProps): JSX.Element;
