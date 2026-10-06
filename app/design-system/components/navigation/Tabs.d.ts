/**
 * Underline tabs — 2px ink rule under the active tab.
 * @startingPoint section="Navigation" subtitle="Underline tabs" viewport="700x160"
 */
export interface TabItem { value: string; label: string; count?: number; }
export interface TabsProps { tabs: (string | TabItem)[]; value?: string; defaultValue?: string; onChange?: (value: string) => void; }
export declare function Tabs(props: TabsProps): JSX.Element;
