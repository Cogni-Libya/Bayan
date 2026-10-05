import * as React from 'react';
/** Short ink label on hover, for icon-only controls. */
export interface TooltipProps { content: React.ReactNode; side?: 'top'|'bottom'; open?: boolean; children: React.ReactNode; }
export declare function Tooltip(props: TooltipProps): JSX.Element;
