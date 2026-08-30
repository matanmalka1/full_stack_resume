# Frontend development

The frontend uses the local FastAPI service as its only backend.

For development, configure the backend process with the exact Vite origin:

```text
CV_API_DEV_ORIGIN=http://127.0.0.1:5173
```

Then run `npm run dev` in this directory. Vite listens on `127.0.0.1:5173` with a strict
port and proxies `/api` to `http://127.0.0.1:8765`. It never falls back to another port,
because that would silently disagree with the backend Origin allowlist.

`npm run build` writes the production bundle to `frontend/dist`. A production caller passes
that directory explicitly as `frontend_dist` to `cv_engine.api.create_app`; FastAPI then
serves assets and React Router entry points under the same origin. `cv web`, process/port
supervision, and browser launch remain M6 work.
