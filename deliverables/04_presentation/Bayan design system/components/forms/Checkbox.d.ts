/** Square checkbox, ink fill when checked. */
export interface CheckboxProps { checked?: boolean; defaultChecked?: boolean; onChange?: (checked: boolean) => void; label?: string; disabled?: boolean; }
export declare function Checkbox(props: CheckboxProps): JSX.Element;
