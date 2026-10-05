import * as React from 'react';
/** Modal dialog on a warm ink scrim. `inline` renders the box without overlay (for docs). */
export interface DialogProps { open?: boolean; title?: string; children?: React.ReactNode; actions?: React.ReactNode; onClose?: () => void; inline?: boolean; width?: number; }
export declare function Dialog(props: DialogProps): JSX.Element | null;
