# React Upgrade Guide

Practical notes for upgrading projects from **React 18 + React Router DOM 6 + MUI 5** to **React 19 + React Router 7 + MUI 6**, and migrating class components to functional components.

---

## 0. Prerequisites

- Node 20+
- TypeScript 4.7+ (React 19 types require it; 5.x is fine)
- If on **Create React App** (`react-scripts`): CRA is unmaintained and does not support React 19. Migrate to **Vite** first. See the [Vite migration guide](https://vitejs.dev/guide/) — the short version is: replace `react-scripts` with `vite` + `@vitejs/plugin-react`, swap `index.html` to the project root, and replace `process.env.REACT_APP_*` with `import.meta.env.VITE_*`.
- **`node-fetch` and other Node.js polyfills**: CRA/webpack silently polyfilled Node.js built-ins (`stream`, `global`, etc.) for browser use. Vite does not. `node-fetch` in particular should simply be deleted — all target browsers have native `fetch` and `Headers`. Grep for `from 'node-fetch'` and remove those imports. Similarly remove any other server-side Node packages that crept into client code.
- **Absolute imports via `baseUrl`**: CRA honoured `tsconfig.json`'s `"baseUrl": "."` to allow imports like `import X from "src/UIComponents/X"`. Vite does not. Either convert those to relative imports, or add a `resolve.alias` in `vite.config.ts`:
  ```ts
  resolve: { alias: { src: '/path/to/src' } }
  ```
  Grep for `from "src/` to find all occurrences.

---

## 1. React Router DOM 6 → React Router 7

React Router v7 ships as a single package (`react-router`), absorbing `react-router-dom`.

### Install

```bash
yarn remove react-router react-router-dom
yarn add react-router@latest
```

If you had a stale `react-router` v5 alongside `react-router-dom` v6 in your `package.json`, both are removed above and replaced by the single v7 package.

### Update imports

All exports previously from `react-router-dom` are now in `react-router`:

```diff
- import { useLocation, useNavigate, BrowserRouter, Routes, Route } from "react-router-dom"
+ import { useLocation, useNavigate, BrowserRouter, Routes, Route } from "react-router"
```

The only exception: `RouterProvider` and `HydratedRouter` (data router APIs) must be imported from `react-router/dom` if you need tree-shaking in non-DOM environments. For most apps using `BrowserRouter` this doesn't matter — import everything from `react-router`.

Bulk-replace imports with your editor or:
```bash
# macOS/Linux
find ./src \( -name "*.tsx" -o -name "*.ts" \) \
  -exec sed -i '' 's|from "react-router-dom"|from "react-router"|g' {} +
```

### Other changes

- `json()` and `defer()` helpers are deprecated. Return plain objects from loaders instead.
- `formMethod` values are now uppercase (`"POST"`, `"GET"`) if you use data-router form handling.
- If using `<Route path="dashboard/*">` with nested relative links, split into parent + child routes (the `v7_relativeSplatPath` behavior is now the default).

No future flags need to be enabled when upgrading from v6 — enabling them in v6 before upgrading is the recommended path, but not mandatory.

---

## 2. MUI 5 → MUI 6

**All MUI packages must be on the same major version.** Before upgrading, align `@mui/material`, `@mui/icons-material`, `@mui/lab`, `@mui/base`, `@mui/system`, `@mui/x-data-grid`, `@mui/x-date-pickers` etc. to v6 simultaneously.

### Pre-upgrade audit

Before touching versions, run this audit to avoid surprises:

**1. Check for version mismatches across all `@mui/*` packages already installed:**
```bash
npm list | grep @mui
```
It is common for packages like `@mui/system` to drift ahead to v7 while `@mui/material` is still on v5. Inconsistent versions compile but produce subtle runtime bugs.

**2. Find all third-party packages that peer-depend on `@mui/material`:**
```bash
cat node_modules/@your-package/package.json | grep '"@mui'
```
Or scan all installed packages at once:
```bash
grep -r '"@mui/material"' node_modules/*/package.json --include="package.json" -l
```
Any package that lists `@mui/material` as a peer dep is a potential blocker. Check whether it supports v6 before committing to the upgrade. Common culprits: query builder UIs, date picker wrappers, data grid wrappers, form libraries.

**3. Identify and remove unused `@mui/*` packages before upgrading:**
`@mui/lab` and `@mui/base` accumulate as CRA boilerplate and are often unused. Check:
```bash
grep -r '@mui/lab\|@mui/base' src/ --include="*.tsx" --include="*.ts" -l
```
Remove any that have no hits. Same for `@mui/x-date-pickers` and `@mui/x-data-grid` — confirm actual usage before keeping them.

> **Gotcha:** A package may not be imported by *your* code but still be required at runtime as a transitive dependency of another package. For example, `@react-awesome-query-builder/mui` internally imports `@mui/x-date-pickers` even if your source never does. If you remove such a package and Rollup/Vite fails at build time with an unresolved import in `node_modules/`, add it back.

**4. Decide on the target version before installing:**
- MUI v7 is available, but third-party MUI wrapper libraries (query builders, etc.) often lag by one major version and may only support up to v6. If you use such a library, target v6 and defer v7 until the library catches up.
- `@mui/x-*` packages (x-data-grid, x-date-pickers) have their own release cycle — v7 of the X packages is compatible with MUI **v6** core.

### Install

```bash
npm install @mui/material@^6 @mui/icons-material@^6 @mui/system@^6 @emotion/react@^11 @emotion/styled@^11 --legacy-peer-deps
# If used:
npm install @mui/x-data-grid@^7 @mui/x-date-pickers@^7 --legacy-peer-deps
```

> **Why `--legacy-peer-deps`?** With React 19 already in the project, many packages haven't formally declared React 19 peer dep support yet even though they work fine at runtime. `npm install` fails hard on these. Use `--legacy-peer-deps` consistently throughout the upgrade. This was likely how the project was originally installed anyway.

> **Stale lock files:** If `npm install` fails with peer dep errors you don't expect, try deleting `node_modules/` and `package-lock.json` and reinstalling from scratch. Lock files can encode old resolution decisions that become invalid after version changes.

### Run codemods

Run the all-in-one codemod first — it covers Grid2 props, ListItem, styled, sx-prop, and more in a single pass:

```bash
npx @mui/codemod@latest v6.0.0/all ./src
```

Or run individual transforms selectively:

```bash
# Grid2 prop changes (xs/sm/md props → size, xsOffset → offset)
npx @mui/codemod@latest v6.0.0/grid-v2-props ./src

# ListItem button prop → ListItemButton
npx @mui/codemod@latest v6.0.0/list-item-button-prop ./src

# theme.palette.mode conditionals → theme.applyStyles()
npx @mui/codemod@latest v6.0.0/styled ./src
npx @mui/codemod@latest v6.0.0/sx-prop ./src
npx @mui/codemod@latest v6.0.0/theme-v6 ./src/theme.ts   # your theme file
```

The codemod does **not** handle `inputProps`/`InputProps` → `slotProps` — those require manual fixes (see below).

### Key breaking changes to fix manually

**`inputProps` / `InputProps` → `slotProps`** — the most common manual migration. Applies to `TextField`, `OutlinedInput`, `Input`, and any component that accepts these props. Grep for `inputProps=` and `InputProps=` to find all occurrences.

```diff
- <TextField
-   inputProps={{ readOnly: true, min: 0 }}
-   InputProps={{ endAdornment: <InputAdornment>...</InputAdornment> }}
- />
+ <TextField
+   slotProps={{
+     htmlInput: { readOnly: true, min: 0 },
+     input: { endAdornment: <InputAdornment>...</InputAdornment> },
+   }}
+ />
```

Mapping:
- `inputProps` (lowercase — HTML `<input>` attributes) → `slotProps.htmlInput`
- `InputProps` (uppercase — the Input wrapper component) → `slotProps.input`

If a component accepts `InputProps` as a **prop** (e.g. a custom `NumberField` that wraps `TextField`), update the destructuring and type accordingly:
```diff
- const { InputProps, ...rest } = this.props;
+ const { slotProps: propsSlotProps, ...rest } = this.props;
```
Then merge `propsSlotProps` into the `slotProps` you pass to `TextField`:
```tsx
slotProps={{
    ...propsSlotProps,
    htmlInput: { ...options, ...(propsSlotProps?.htmlInput as object) },
    input: { ...inputOptions, ...(propsSlotProps?.input as object) },
}}
```

**Grid2 stabilized** — the import changed:
```diff
- import { Unstable_Grid2 as Grid2 } from '@mui/material';
+ import { Grid2 } from '@mui/material';
```

**ListItem** — `button`, `autoFocus`, `disabled`, `selected` props removed; use `ListItemButton` directly:
```diff
- <ListItem button onClick={...}>
+ <ListItemButton onClick={...}>
```

**Typography `color` prop** — no longer a system prop; use `sx`:
```diff
- <Typography color={(theme) => theme.palette.primary.main}>
+ <Typography sx={{ color: (theme) => theme.palette.primary.main }}>
```

**`LoadingButton`** — removed from `@mui/lab` in v6.4+; loading state is now a standard `Button` prop:
```diff
- import { LoadingButton } from '@mui/lab';
+ import { Button } from '@mui/material';
- <LoadingButton loading={...}>
+ <Button loading={...}>
```

**`styled(Box)`** — `component` prop removed from `BoxOwnProps`; switch to a concrete element:
```diff
- const StyledBox = styled(Box)`color: white;`;
+ const StyledDiv = styled('div')`color: white;`;
```

**`CssVarsProvider` / `extendTheme`** — experimental prefix removed:
```diff
- import { experimental_extendTheme as extendTheme, Experimental_CssVarsProvider as CssVarsProvider } from '@mui/material/styles';
+ import { extendTheme, CssVarsProvider } from '@mui/material/styles';
```

**Tests** — ripple timing changed; button-click tests now need `act`:
```diff
- fireEvent.click(button);
+ await act(async () => fireEvent.click(button));
```

### Unrelated issues often surfaced during this upgrade

The MUI upgrade tends to trigger `npm install` failures caused by other stale dependencies that were previously hidden behind a lock file. Treat these as separate clean-up tasks:

**Unused packages that commonly conflict with React 19:**
- `@testing-library/react@13` — requires React 18; remove if there are no tests, or upgrade to v16+
- `react-leaflet@4` — requires React 18; upgrade to v5+ or remove if unused
- `react-date-picker@9` — requires React 16–18; upgrade or remove

**`require()` in a TypeScript/Vite project** — Vite uses ESM; `require` is not available. Convert to `import`:
```diff
- const shuffler = require('shuffle-seed');
+ import shuffler from 'shuffle-seed';
```
If the imported package has no type declarations, install `@types/<package>` or add a `declare module` shim.

**`replaceAll` TypeScript error** — if you see `Property 'replaceAll' does not exist on type 'string'`, your `tsconfig.json` targets ES2020 or earlier. Bump to ES2021:
```diff
- "target": "ES2020",
- "lib": ["dom", "dom.iterable", "ES2020"],
+ "target": "ES2021",
+ "lib": ["dom", "dom.iterable", "ES2021"],
```

---

## 3. React 18 → React 19

### Install

```bash
yarn add react@^19 react-dom@^19
yarn add -D @types/react@^19 @types/react-dom@^19
```

### Run codemods

```bash
# All JS/JSX breaking-change codemods in one shot:
npx codemod@latest react/19/migration-recipe

# TypeScript-specific type fixes:
npx types-react-codemod@latest preset-19 ./src
```

### Key breaking changes

**`useRef` now requires an argument** — `useRef()` with no argument is a TypeScript error:
```diff
- const ref = useRef();
+ const ref = useRef<HTMLDivElement>(null);
```
The codemod handles most of these (`refobject-defaults`).

**Ref callback return value** — must be `void` or `undefined`; returning a value is now a type error:
```diff
- <div ref={el => (this.el = el)} />
+ <div ref={el => { this.el = el; }} />
```
Codemod: `npx types-react-codemod@latest no-implicit-ref-callback-return ./src`

**`ReactElement.props` defaults to `unknown`** (was `any`) — code that accessed element props without type guards will now fail. Use the `react-element-default-any-props` codemod if you need to preserve the `any` behavior temporarily.

**`propTypes` and `defaultProps` silently removed** — in a TypeScript project these are typically not used, but double-check. `defaultProps` on function components was already deprecated in v18.

**Legacy context API removed** — `contextTypes` / `getChildContext`. Migrate to `React.createContext`.

**`ReactDOM.render` / `ReactDOM.hydrate` removed** — use `createRoot` / `hydrateRoot` (already required in v18).

**Global JSX namespace removed** — if any `.d.ts` files augment `namespace JSX`, wrap them:
```diff
- namespace JSX { interface IntrinsicElements { ... } }
+ declare module "react/jsx-runtime" { namespace JSX { interface IntrinsicElements { ... } } }
```

**StrictMode double-invokes ref callbacks** — if you see ref effects firing twice in dev, this is expected.

---

## 4. Class Components → Functional Components

This can be done incrementally at any point — functional and class components interoperate freely.

### The conversion pattern

```tsx
// BEFORE — class component
interface IProps { value: string }
interface IState { count: number }

class MyComponent extends React.Component<IProps, IState> {
    constructor(props: IProps) {
        super(props);
        this.state = { count: 0 };
    }
    componentDidMount() { document.title = this.props.value; }
    componentDidUpdate(prevProps: IProps) {
        if (prevProps.value !== this.props.value) document.title = this.props.value;
    }
    componentWillUnmount() { document.title = ''; }
    increment = () => this.setState(curr => ({ count: curr.count + 1 }));
    render() { return <button onClick={this.increment}>{this.state.count}</button>; }
}
```

```tsx
// AFTER — functional component
function MyComponent({ value }: IProps) {
    const [count, setCount] = useState(0);

    useEffect(() => {
        document.title = value;
        return () => { document.title = ''; };
    }, [value]);

    return <button onClick={() => setCount(c => c + 1)}>{count}</button>;
}
```

### Mapping patterns

| Class | Functional |
|---|---|
| `this.state = { x }` | `const [x, setX] = useState(...)` |
| `this.setState({ x })` | `setX(...)` |
| `this.setState(curr => ...)` | `setX(curr => ...)` |
| `componentDidMount` | `useEffect(() => {...}, [])` |
| `componentWillUnmount` | return cleanup from `useEffect` |
| `componentDidUpdate(prevProps)` | `useEffect(() => {...}, [dep])` — React handles the comparison |
| `this.props.x` | destructure from params: `{ x }` |
| Instance methods | plain functions inside the component (or `useCallback` if passed as props) |
| `createRef` / `this.myRef` | `useRef` |

### `componentDidUpdate` with `setState` callback

The pattern `this.setState(update, callback)` has no direct hook equivalent. Replace with `useEffect`:

```tsx
// BEFORE
this.setState({ loading: true }, async () => {
    const data = await fetch(...);
    this.setState({ data, loading: false });
});

// AFTER — trigger the async work from a useEffect that watches `loading`
const [loading, setLoading] = useState(false);
useEffect(() => {
    if (!loading) return;
    fetch(...).then(data => { setData(data); setLoading(false); });
}, [loading]);
// then call setLoading(true) to trigger it
```

Or, more simply, just call the async function directly — you don't need a setState callback:
```tsx
const loadData = async () => {
    setLoading(true);
    const data = await fetch(...);
    setData(data);
    setLoading(false);
};
```

---

## 5. HOCs → Hooks

Higher-order components exist to inject props into class components. With functional components, inject the same values via hooks directly.

### `withRouter` pattern

Instead of wrapping a class component with a `withRouter` HOC, call the hooks inside the functional component:

```tsx
// BEFORE
class MyPage extends React.Component<IProps & IRouterProps, IState> { ... }
export default withRouter(MyPage);

// AFTER
function MyPage(props: IProps) {
    const params = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const [searchParams, setSearchParams] = useSearchParams();
    ...
}
export default MyPage;
```

Delete `withRouter.tsx` once all consumers are converted.

### Context HOCs (`withKeyStates`, etc.)

Replace `Context.Consumer` HOCs with the corresponding `useContext` hook:

```tsx
// BEFORE — class component wrapped in withKeyStates HOC
class MyComponent extends React.Component<IProps & KeyStatesContextType, IState> { ... }
export default withKeyStates(MyComponent);

// AFTER — functional component calling the hook directly
function MyComponent(props: IProps) {
    const { shiftKey, ctrlKey } = useKeyStates();
    ...
}
export default MyComponent;
```

Delete `withKeyStates.tsx` once all consumers are converted.

### Error suppression HOC

A HOC that only runs a `useEffect` can be inlined into the component, or extracted as a custom hook:

```tsx
// Instead of: export default withReactErrorSuppression(App)
// Inline the effect directly in the App component's useEffect, or:

function useResizeObserverSuppression() {
    useEffect(() => {
        const hide = (e: ErrorEvent) => {
            if (e.message === 'ResizeObserver loop completed with undelivered notifications.') {
                document.getElementById('webpack-dev-server-client-overlay')?.setAttribute('style', 'display: none');
            }
        };
        window.addEventListener('error', hide);
        return () => window.removeEventListener('error', hide);
    }, []);
}
```

### PubSub subscriptions in class components

PubSub `subscribe` / `unsubscribe` in class lifecycles maps directly to `useEffect`:

```tsx
// BEFORE
constructor() { PubSub.subscribe(events.alert, this.handleAlert); }
componentWillUnmount() { PubSub.clearAllSubscriptions(); }

// AFTER
useEffect(() => {
    const token = PubSub.subscribe(events.alert, handleAlert);
    return () => PubSub.unsubscribe(token);
}, []);
```

Use `PubSub.unsubscribe(token)` (not `clearAllSubscriptions`) so only this component's subscriptions are cleaned up.

---

## 6. Anti-Patterns to Fix During Conversion

The class→functional migration is a good opportunity to fix anti-patterns that work by accident in class components but are clearly wrong in functional ones.

### Direct state mutation

Class components store all state in one object; devs sometimes mutate a sub-object before calling `setState`. This is always wrong — React requires state to be immutable — but class components sometimes render correctly anyway.

```tsx
// BEFORE — mutating state directly, then calling setState
private fetchPostDetails = async () => {
    const post = this.state.post;
    post.data = await fetchPostData(itemId); // ← mutates the state object
    this.setState({ post });
};

// AFTER — produce a new object
const fetchDetails = async () => {
    const data = await fetchPostData(itemId);
    setPost(curr => ({ ...curr, data }));
};
```

### Direct prop mutation

Same problem, but worse — props should never be mutated:

```tsx
// BEFORE
this.props.media.media_parts = await fetchMediaParts(itemId);
this.setState(curr => ({ ...curr }));

// AFTER — store in local state, not in the prop object
const parts = await fetchMediaParts(itemId);
setMedia(curr => ({ ...curr, media_parts: parts }));
```

### `setState(update, callback)` — the setState callback anti-pattern

The second argument to `setState` is a callback that runs *after* the re-render. It is commonly misused as a way to "read fresh state" before doing async work. In functional components, just do the async work in the same function — no callback needed:

```tsx
// BEFORE — setState callback used to ensure state is committed before async fetch
this.setState({ loading: true }, async () => {
    const data = await fetchData(this.state.id); // reads state after commit
    this.setState({ data, loading: false });
});

// AFTER — no callback needed; async work runs sequentially
setLoading(true);
const data = await fetchData(id); // just use the variable directly
setData(data);
setLoading(false);
```

---

## 7. URL as Source of Truth (URL-driven State)

When a page's state can be encoded in the URL (search queries, filters, pagination), treat the URL as the single source of truth rather than storing a parallel copy in component state.

**Pattern:** derive state from `useSearchParams()` on every render; use `navigate` to update the URL when the user changes something.

```tsx
// Derive query directly from URL on every render — no useState needed
const [searchParams] = useSearchParams();
const query = extractQueryFromParams(searchParams); // pure function

// useEffect fires when URL changes — handles both initial load and navigation
useEffect(() => {
    fetchData(query);
}, [searchParams]);

// User actions update the URL, which triggers the effect above
const performSearch = (overrides?: Partial<ISearchQuery>) => {
    const newParams = buildParams({ ...query, ...overrides });
    navigate({ search: newParams }, { replace: true });
};
```

Benefits:
- Back/forward browser navigation works automatically
- Shareable URLs for any search state
- No stale-state bugs between `query` variable and `searchParams`

**Use `useRef` for non-rendering state** (like in-flight request handles):

```tsx
const abortControllerRef = useRef<AbortController | null>(null);
// ...inside effect:
abortControllerRef.current?.abort();
const controller = new AbortController();
abortControllerRef.current = controller;
fetchData({ signal: controller.signal }).then(...);
```

`useRef` is the right tool for values that need to persist across renders but don't trigger re-renders when they change.
