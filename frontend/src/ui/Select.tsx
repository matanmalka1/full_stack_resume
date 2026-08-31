import type { SelectHTMLAttributes } from "react";

import { cx } from "./cx";
import { controlClasses } from "./TextInput";

const chevron =
  "bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2016%2016%22%20fill%3D%22none%22%20stroke%3D%22%235b6577%22%20stroke-width%3D%221.75%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M4%206l4%204%204-4%22%2F%3E%3C%2Fsvg%3E')] bg-[length:1rem_1rem] bg-no-repeat bg-[position:left_0.875rem_center] rtl:bg-[position:left_0.875rem_center] ltr:bg-[position:right_0.875rem_center] pe-10 appearance-none";

export const Select = ({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) => {
  return <select className={cx(controlClasses, "min-h-11", chevron, className)} {...rest} />;
};
