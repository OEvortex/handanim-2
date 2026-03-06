## 1. Overview

Implement a small Manim-compat transform layer on top of handanim’s existing morph system.

Goals:
- Map the classes listed on Manim’s `animation.transform` docs page to pragmatic handanim equivalents.
- Reuse `TransformAnimation` / `ReplacementTransformAnimation` wherever possible.
- Add a clean late-binding hook for classes whose target drawable must be derived from the source at `Scene.add()` time.
- Add a scene-aware expansion hook for classes that conceptually operate on multiple drawables.

Success criteria:
- Thin aliases behave like Manim-named wrappers over current morph behavior.
- Lazy wrappers can derive a target from the source drawable without the caller pre-building it.
- Multi-drawable wrappers expand into existing low-level scene events and work with `DrawableGroup`.

Scope boundaries:
- In scope: wrapper classes, late target resolution, multi-drawable expansion, exports, tests.
- Out of scope for MVP: full `TransformAnimations` parity; arbitrary pointwise geometry if no reusable ops helper exists yet.

## 2. Prerequisites

- No new dependencies or migrations.
- Preserve the current immutable drawable pattern (`translate/scale/rotate` return new drawables).
- Confirm clockwise/counterclockwise `path_arc` sign against current `_interpolate_point_along_arc` behavior before finalizing wrappers.

## 3. Implementation Steps

### Step 1: Add the Manim-name wrapper surface
- Create `src/handanim/animations/transform_compat.py`.
- Implement thin wrappers that directly delegate to current morph classes:
  - `Transform` -> `TransformAnimation`
  - `ReplacementTransform` -> `ReplacementTransformAnimation`
  - `ClockwiseTransform` -> `TransformAnimation` with fixed clockwise `path_arc`
  - `CounterclockwiseTransform` -> `TransformAnimation` with fixed counterclockwise `path_arc`
  - `FadeTransform` -> pragmatic wrapper over `ReplacementTransformAnimation`
- Export them from `src/handanim/animations/__init__.py`.
- Testing: constructor/default tests and one path-arc direction test.

### Step 2: Add lazy target generation for source-derived transforms
- Modify `src/handanim/core/scene.py` so `Scene.add()` checks for an event hook like `resolve_target_drawable(source_drawable, scene)` before the existing `target_drawable` binding path.
- Use that hook for wrappers whose target is derived from the source drawable at add-time:
  - `ApplyFunction`
  - `ApplyMethod` (initially only for methods that already return new drawables, e.g. `translate`, `scale`, `rotate`)
  - `MoveToTarget`
  - `ScaleInPlace`
  - `ShrinkToCenter`
- Add minimal drawable-side state helpers in `src/handanim/core/drawable.py` only if needed for ergonomics:
  - `target` storage for `MoveToTarget`
  - saved-state snapshot support for future `Restore`
- Testing: verify the target is resolved late, not at wrapper construction time.

### Step 3: Add deferred / secondary lazy wrappers
- Build the next tier on the same late-binding hook:
  - `ApplyMatrix`
  - `ApplyComplexFunction`
  - `ApplyPointwiseFunction`
  - `ApplyPointwiseFunctionToCenter`
  - `FadeToColor`
  - `Restore`
- Prefer wrappers that synthesize a target drawable; if a true drawable clone/style-copy API is too invasive, defer `FadeToColor` and `Restore` behind explicit `NotImplementedError` with a documented reason.
- Testing: add focused coverage only for the wrappers that are actually implemented in this phase.

### Step 4: Add scene-aware expansion for multi-drawable semantics
- Extend `Scene.add()` with an optional event hook like `expand_for_scene(scene, drawable)` that can fan one high-level request out into several `(event, drawable)` additions.
- Use it for:
  - `FadeTransformPieces` -> normalize to `DrawableGroup` piecewise replacement, leveraging existing group pairing / `EmptyDrawable` support.
  - `CyclicReplace` -> expand to a cycle of `ReplacementTransformAnimation`s.
  - `Swap` -> 2-item `CyclicReplace`.
  - `TransformFromCopy` -> create a temporary copy-like drawable, keep the original visible, transform the temporary drawable to target.
- Keep `FadeTransformPieces` compatible with current `DrawableGroup` matching in `Scene.add()`.
- Testing: visibility/timeline assertions plus final-frame bbox checks for group cases.

### Step 5: Explicitly defer the non-pragmatic class
- Mark `TransformAnimations` unsupported for now.
- Reason: handanim animations are scene events, not drawable-like animation objects that can themselves be interpolated.
- Export policy: either omit it entirely or ship a stub that raises `NotImplementedError` with guidance.

## 4. File Changes Summary

Created:
- `src/handanim/animations/transform_compat.py`

Modified:
- `src/handanim/core/scene.py`
- `src/handanim/core/drawable.py`
- `src/handanim/animations/__init__.py`
- `tests/test_morph.py`

Optional:
- `examples/morph_demo.py` or a new focused demo if manual verification is needed.

## 5. Testing Strategy

- Unit tests for thin wrapper aliases and `path_arc` defaults.
- Unit tests for late target resolution (`ApplyFunction`, `ApplyMethod`, `MoveToTarget`).
- Group-expansion tests for `FadeTransformPieces`, `Swap`, and `CyclicReplace`.
- Timeline/visibility tests for `ReplacementTransform`-style wrappers and `TransformFromCopy`.
- Small manual smoke test by rendering a short morph demo after the unit tests pass.

## 6. Rollback Plan

- Revert the compat wrapper file and export changes.
- Remove the new `Scene.add()` hooks if they complicate existing event flow.
- Keep core `TransformAnimation` / `ReplacementTransformAnimation` untouched so rollback is low risk.

## 7. Estimated Effort

- Effort: 1-2 days for MVP wrappers + tests; 2-4 days if matrix/pointwise/stateful wrappers are included.
- Complexity: medium.

## Quick Mapping Reference

- Thin wrappers: `Transform`, `ReplacementTransform`, `ClockwiseTransform`, `CounterclockwiseTransform`, `FadeTransform`.
- Lazy target generation: `ApplyFunction`, `ApplyMethod`, `MoveToTarget`, `ScaleInPlace`, `ShrinkToCenter`, later `ApplyMatrix`, `ApplyComplexFunction`, `ApplyPointwiseFunction`, `ApplyPointwiseFunctionToCenter`, `FadeToColor`, `Restore`.
- Scene-aware expansion: `FadeTransformPieces`, `CyclicReplace`, `Swap`, `TransformFromCopy`.
- Defer/unsupported: `TransformAnimations`.

