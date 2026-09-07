# Feature modules

Each directory in this folder owns one business capability. Its `index.ts` is the
public interface consumed by `app/`; route components live in `pages/`, reusable
feature UI lives in `components/`, and non-UI domain presentation belongs in `model/`.

`app/` owns composition and routing, `ui/` contains only domain-independent
primitives, and `api/` remains the shared HTTP transport boundary. A feature may use
another feature only through an explicitly exported interface, not through its route
page or a deep internal import.
