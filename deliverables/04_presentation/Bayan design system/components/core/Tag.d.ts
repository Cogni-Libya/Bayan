import * as React from 'react';
/** Selectable/removable chip for genres, topics and filters. */
export interface TagProps { selected?: boolean; onClick?: () => void; onRemove?: () => void; children: React.ReactNode; style?: React.CSSProperties; }
export declare function Tag(props: TagProps): JSX.Element;
