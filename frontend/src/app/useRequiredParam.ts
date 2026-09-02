import { useParams } from "react-router-dom";

/** Read a route parameter whose presence is guaranteed by the owning route shape. */
export const useRequiredParam = (name: string): string => {
  const value = useParams()[name];
  if (value === undefined) {
    throw new Error(`Route rendered without a ${name} route parameter`);
  }
  return value;
};
