# Feature modules

Each directory in this folder owns one business capability. Its `index.ts` is the
public interface consumed by `app/`; route components live in `pages/`, reusable
feature UI lives in `components/`, and non-UI domain presentation belongs in `model/`.

`app/` owns composition and routing, and a feature may use another feature only
through an explicitly exported interface, not through its route page or a deep
internal import.

## Where server state lives

`src/api/` owns the transport and the cache identity of each server resource: the
request functions, and the query key and `queryOptions` that name the resource. Both
belong there because several features read the same resource and every writer has to
invalidate it by the same key — an Application's projection is read by four features,
and a working draft by two — so an owning feature could not hold the key without the
others importing that feature to invalidate it.

`features/<f>/api/` owns that feature's composition on top: `queries.ts` for reads it
narrows (`select`, `enabled`, dependent reads) and `mutations.ts` for the commands it
sends together with the invalidation each one implies. Only where such composition
exists — a feature with no query or mutation of its own has no `api/` folder.

`features/<f>/hooks/` owns hooks that hold local, form, or UI state, even when they
also read or write the server: what puts a hook here is the state the server never
sees. A mutation used by exactly one component stays inside that component.

## What `ui/` may not know

`ui/` contains only domain-independent primitives. It owns how loud something is —
the five tones in `tone.ts` — and never which domain value maps to which tone: a
preparation state, a recruitment status, and an analysis fit are named and toned by
the feature that owns them and reach `ui` already reduced to a tone.
