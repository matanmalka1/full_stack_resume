import { type FieldValues, type UseFormProps, type UseFormReturn, useForm } from "react-hook-form";

export const useAppForm = <TFields extends FieldValues>(options?: UseFormProps<TFields>): UseFormReturn<TFields> => {
  return useForm<TFields>({
    mode: "onBlur",
    reValidateMode: "onChange",
    ...options,
  });
};
