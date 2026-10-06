import * as React from 'react';
/**
 * Surface container. Outlined is the default — borders over shadows.
 * @startingPoint section="Core" subtitle="Card surfaces" viewport="700x300"
 */
export interface CardProps extends React.HTMLAttributes<HTMLDivElement> { variant?: 'outlined'|'elevated'|'sunken'|'inverse'; padding?: 'none'|'sm'|'md'|'lg'; interactive?: boolean; children?: React.ReactNode; }
export declare function Card(props: CardProps): JSX.Element;
