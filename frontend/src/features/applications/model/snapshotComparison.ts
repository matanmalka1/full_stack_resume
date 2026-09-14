/* A bounded contiguous edit: common Unicode prefix/suffix stay unmarked. The
   changed region can include unchanged text between edits; no quadratic diff
   matrix or truncation is needed even for the largest accepted posting. */
export const snapshotComparison = (before: string, after: string) => {
  const left = Array.from(before);
  const right = Array.from(after);
  let start = 0;
  while (start < left.length && start < right.length && left[start] === right[start]) start++;
  let end = 0;
  while (
    end < left.length - start &&
    end < right.length - start &&
    left[left.length - end - 1] === right[right.length - end - 1]
  )
    end++;
  return {
    prefix: left.slice(0, start).join(""),
    removed: left.slice(start, left.length - end).join(""),
    added: right.slice(start, right.length - end).join(""),
    suffix: end === 0 ? "" : left.slice(left.length - end).join(""),
  };
};
