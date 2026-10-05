/** Radio group. The selected dot is ochre — a nod to the logo's sun. */
export interface RadioOption { value: string; label: string; }
export interface RadioProps { name?: string; options: (string | RadioOption)[]; value?: string; defaultValue?: string; onChange?: (value: string) => void; direction?: 'row' | 'column'; }
export declare function Radio(props: RadioProps): JSX.Element;
