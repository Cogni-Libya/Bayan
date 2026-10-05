import * as React from 'react';
/** Native select styled as a Bayan field. */
export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> { label?: string; hint?: string; error?: string; options: (string | { value: string; label: string })[]; }
export declare function Select(props: SelectProps): JSX.Element;
