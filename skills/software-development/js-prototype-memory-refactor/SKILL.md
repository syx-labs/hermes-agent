---
name: js-prototype-memory-refactor
description: Reduce JS object memory with shared prototypes.
version: 0.1.0
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [JavaScript, Performance, Memory, Refactoring, Benchmarking]
---

# Shared Prototype Memory Refactor

Use this skill to reduce retained JavaScript heap when a library or app creates many repeated internal objects, as highlighted by TanStack Table V9's row/column/cell/header refactor. It does not replace pagination, virtualization, server-side data loading, or normal product judgment about whether huge client-side datasets are appropriate. Dependency stance: stdlib-free procedure through Hermes tools; project-specific benchmark commands depend on the target repo, and the TanStack benchmark source uses `pnpm`, Playwright, Chrome DevTools Protocol, and production Vite builds.

## When to Use

- A JS/TS table, grid, tree, parser, graph, or state engine creates thousands to millions of similar objects.
- Heap snapshots show many duplicate functions, closures, or method properties attached to per-instance objects.
- A user asks to investigate browser memory growth, retained JS heap, or 4GB-limit crashes in large client-side datasets.
- A refactor should improve memory without changing public behavior.
- You need to compare TanStack Table V8/V9-style memory behavior or reproduce the published benchmark method.

## Prerequisites

- No credentials or environment variables are required.
- Access to the target codebase through `read_file`, `search_files`, and `patch`.
- A representative workload with fixed rows, columns, features, and interactions.
- A repeatable test/build/benchmark command invoked through the `terminal` tool.
- For the published TanStack benchmark repo, run `pnpm install` before benchmarks.
- For browser retained-heap measurement, use a harness that can run a production build, open a fresh Chromium context, force garbage collection, and record heap after GC; the TanStack source uses Playwright plus Chrome DevTools Protocol.

## How to Run

1. Use `search_files` to locate object factories, row/column/cell/header model creation, and any existing memory or performance benchmark scripts.
2. Use `read_file` to inspect the hot constructors/factories and benchmark documentation before editing.
3. Invoke the baseline benchmark through the `terminal` tool and record retained JS heap after forced GC plus rendered row/cell or equivalent correctness counts.
4. Use `patch` to move stable per-object methods from instance literals/closures onto a shared prototype while keeping per-object data on each instance.
5. Invoke the same benchmark through the `terminal` tool and compare before/after results for the same workload.

## Quick Reference

- `pnpm install`
- `pnpm bench:memory`
- `pnpm bench:memory -- --iterations 5 --overscan 5`
- `pnpm bench:memory -- --benchmark rows`
- `pnpm bench:memory -- --benchmark columns`
- `pnpm bench:memory -- --benchmark paginated-rows`
- `pnpm bench:memory -- --benchmark kitchen-sink`
- `pnpm bench:memory -- --heapSnapshots true`
- `pnpm bench:memory -- --heapSnapshots true --maxSnapshotCells 100000`
- `pnpm bench:memory -- --maxSmoothScrollCells 10000000`
- `pnpm bench:performance`
- `pnpm bench:performance -- --iterations 3 --warmups 0`
- `pnpm bench:performance -- --operation sorting`
- `pnpm bench:performance -- --operation filtering --scenario includesString`
- `pnpm bench:performance -- --operation aggregation --scenario sum`
- `pnpm bench:performance -- --rows 30000,300000`

## Procedure

1. **Define the object graph under test.** Pick one hot family at a time: rows, columns, cells, headers, or the target app's equivalent repeated internal object. Done when the before/after workload, object family, and success metric are written down.

2. **Capture a baseline before editing.** Through `terminal`, run the existing production-like memory benchmark or the closest reproducible scenario. Record retained JS heap after forced GC, DOM or rendered-object counts, and the exact interactions measured, such as initial render, pagination, instant scroll, or smooth scroll.

3. **Identify duplicated per-instance behavior.** Use `search_files` and `read_file` to inspect factories/constructors for methods attached directly to every object, especially arrow functions or closures that repeat for each row/cell/header. Treat the duplicated method/closure shape as the suspect; do not change behavior yet.

4. **Choose the shared prototype boundary.** Keep unique data on each instance and move stable behavior onto one shared prototype for that object family. The method should read instance state from `this` or from explicit instance fields instead of closing over fresh per-instance scopes unless the closure is genuinely unique.

5. **Patch narrowly.** Use `patch` to refactor one object family at a time. Preserve the public API, feature semantics, tests, file style, and object data shape; do not mix this with formatting, feature changes, or unrelated CPU optimization.

6. **Run correctness checks first.** Through `terminal`, run the repo's tests/typecheck/build command. If behavior changed, stop and fix the regression before trusting any memory number.

7. **Rerun the exact same memory scenario.** Use the same row/column counts, features, browser path, interaction phases, and iteration count. Compare retained JS heap after forced GC, not only transient heap before GC.

8. **Interpret by scale.** Expect little or no visible gain for tiny tables; the TanStack V9 article showed the large savings appearing as processed cells grew. At 1,000,000 rows × 8 columns, the reported Table V9 retained heap was over 2.4GB lower than V8, while tiny examples were near noise and one small kitchen-sink case used slightly more memory.

9. **Guard CPU tradeoffs.** If the refactor adds memoization or changes call shape, run the operation/performance benchmark too. The TanStack benchmark repo includes sorting, filtering, and aggregation operation benchmarks for this reason.

## Pitfalls

- Virtualization reduces DOM work, but it may not reduce all internal model objects; still measure retained JS heap.
- Small workloads can hide the effect. The prototype refactor matters most when object count is large enough for duplicate methods and closures to dominate.
- Do not declare success from memory before forced GC; record retained heap after garbage collection.
- Heap snapshots can become multiple GB. The TanStack benchmark captures snapshots by default only for configurations up to 10,000 estimated cells and provides `--maxSnapshotCells` for explicit overrides.
- Smooth-scroll capture may be skipped for very large configurations. The source benchmark records initial and instant-scroll phases plus a `smooth-scroll-skipped` marker beyond its smooth-scroll limit.
- Browser memory limits are not product permission to load huge datasets client-side. TanStack's article notes that 10–16 million rows may be technically possible in the table engine, but real apps often hit limits earlier.
- Do not merge prototype refactors with public API changes. If a regression appears, the diff must be small enough to isolate root cause.

## Verification

Run through the `terminal` tool: `pnpm bench:memory -- --iterations 5 --overscan 5`. The skill worked only if the before/after run uses equivalent rendered row/cell counts and the retained JS heap after forced GC drops at the target scale, or a small-table neutral result is explicitly explained.
