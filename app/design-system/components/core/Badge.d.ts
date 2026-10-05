import * as React from 'react';
/** Small status pill — reading status, counts, "new". Non-interactive. */
export interface BadgeProps { tone?: 'neutral'|'accent'|'success'|'danger'|'info'|'ink'; dot?: boolean; children: React.ReactNode; style?: React.CSSProperties; }
export declare function Badge(props: BadgeProps): JSX.Element;
