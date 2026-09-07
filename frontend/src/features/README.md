# Feature modules

Each directory in this folder owns one business capability. Its `index.ts` is the
public interface consumed by `app/`; route components live in `pages/`, reusable
feature UI lives in `components/`, and non-UI domain presentation belongs in `model/`.

`app/` owns composition and routing, and a feature may use another feature only
through an explicitly exported interface, not through its route page or a deep
internal import.

## Where server state lives

`src/api/` owns the transport and the cache contract of each server resource: the
request functions, the query key and `queryOptions` that name it, and the fan-out a
change to it implies — `invalidateApplicationViews` is there because "an Application
changed" always means its detail read and the board's list read, which is a fact about
the resource rather than about any feature.

The contract belongs there because several features read the same resource: an
Application's projection is read by four and a working draft by two, so an owning
feature could not hold the key without the others importing that feature to invalidate
it. Features still decide *when* to invalidate; they do not decide *what*.

`features/<f>/api/` owns that feature's composition on top: `queries.ts` for reads it
narrows (`select`, `enabled`, dependent reads) and `mutations.ts` for the commands it
sends together with the invalidation each one implies. Only where such composition
exists — a feature with no query or mutation of its own has no `api/` folder.

`features/<f>/hooks/` owns hooks a component reaches for to hold state: a form, a
dialog's answer, a debounced field, or an id a page keeps across a transition. A
mutation used by exactly one component stays inside that component.

The line between the two is what the module is *for*, not whether it calls `useState`:
`api/mutations.ts` may track the id of work it queued, because that id only exists to
gate the next command; a dialog's decision belongs to the screen that opens the dialog,
and reaches the command as an argument.

## What `ui/` may not know

`ui/` contains only domain-independent primitives. It owns how loud something is —
the five tones in `tone.ts` — and never which domain value maps to which tone: a
preparation state, a recruitment status, and an analysis fit are named and toned by
the feature that owns them and reach `ui` already reduced to a tone.
