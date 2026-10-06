import * as React from 'react';
/**
 * Text field with label, hint and error.
 * @startingPoint section="Forms" subtitle="Form controls" viewport="700x360"
 */
export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> { label?: string; hint?: string; error?: string; }
export declare function Input(props: InputProps): JSX.Element;
