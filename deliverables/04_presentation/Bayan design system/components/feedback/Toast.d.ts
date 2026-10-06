import * as React from 'react';
/** Brief ink-colored notification with a tone dot and optional action. */
export interface ToastProps { tone?: 'neutral'|'accent'|'success'|'danger'; children: React.ReactNode; action?: React.ReactNode; onClose?: () => void; }
export declare function Toast(props: ToastProps): JSX.Element;
