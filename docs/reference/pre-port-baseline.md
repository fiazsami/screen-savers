# The pre-port baseline

What the three savers do on macOS 26, recorded **before** any Metal branch opens.

This exists because of `ss-pl9`, and because of one asymmetry: once a port lands
you can never go back and capture the "before" picture. If a ported saver renders
black, an uncaptured baseline cannot tell you whether the port broke it or whether
it was already broken.

The *why* behind the port sequencing lives in [`doctrine.md`](doctrine.md); the
harness that measures the code lives in [`tooling.md`](tooling.md).

> **Status.** The headline result is in: **all three savers run and render
> correctly on macOS 26**, observed from System Settings on 2026-08-22. That is
> the first time anything in this project has verified a pixel. Everything the
> 398 characterization cases prove is about where a vertex *is*; none of it is
> about whether anything appears on screen.
>
> The record below is therefore in two halves, and they have different
> standing. The **code-path** half is read out of the source and is as reliable
> as reading. The **observational** half is one person watching three savers
> once, and it is thin — see *What this baseline does not cover*.

## What was observed

| saver | target | result |
| --- | --- | --- |
| helios | `Helios.saver` | runs, renders correctly |
| hyperspace | `Hyperspace.saver` | runs, renders correctly |
| hills | `Hills.saver` | runs, renders correctly |

All three installed to `~/Library/Screen Savers` from a local ad-hoc build and
were selected and previewed from System Settings → Screen Saver. Locally built
bundles carry no `com.apple.quarantine` attribute, so no Gatekeeper assessment
was involved.

## What the code path actually is, which is not what `ss-pl9` assumed

`ss-pl9` framed the risk as hyperspace's four GLSL 1.20 shaders being "loaded
through ARB entry points on top of a hand-rolled `queryExtension` that parses
`glGetString(GL_EXTENSIONS)`", and called it unknown whether that still works on
a current driver.

**On macOS none of that code compiles.** Checked in both twins:

| | where | status on macOS |
| --- | --- | --- |
| `initExtensions()` | `Hyperspace/extensions.cpp:76` | inside a `/* … */` block — **not compiled** |
| its declaration | `Hyperspace/extensions.h:46` | also inside the comment |
| its only call | `Hyperspace/Hyperspace.cpp:505` | inside `#ifdef WIN32` (opened at 487) |
| free `queryExtension()` | `Hyperspace/extensions.cpp:39` | compiled, **no live caller** |
| `impSurface::queryExtension()` | `Implicit/impSurface.cpp:94` | inside `#ifdef WIN32` |
| the VBO capability check + fallback | `Implicit/impSurface.cpp:42–58` | inside `#ifdef WIN32` |

So the ARB and VBO entry points are not resolved at runtime on macOS at all —
they bind at **link time** against the OpenGL framework. The extension-string
parsing that looked like the fragile part is Windows-only.

Two consequences, and the second is the one that matters for the port:

**The good one.** `glGetString(GL_EXTENSIONS)` returns `NULL` in a core profile,
which would have made that parser walk a null pointer. It cannot, because it is
not compiled. One less way for the pre-port state to be quietly broken.

**The load-bearing one.** `impSurface::impSurface()` sets `mUseVBOs = true`
unconditionally, and the entire *"if any extensions were not found, fall back to
draw arrays"* path is `#ifdef WIN32`. **There is no fallback on macOS.** The same
is true of shaders: `setDefaults()` sets `dShaders = 1`, `initShaders()` runs
whenever it is set, and nothing anywhere checks a compile or link status —
grepped for `COMPILE_STATUS`, `LINK_STATUS` and `InfoLog`, no hits in either twin.

`HyperspaceView.mm:76` carries the comment *"must do this before
`RSSShadersSupported()` will work"*. **`RSSShadersSupported` does not exist** —
that comment is its only occurrence in the repository. The macOS capability gate
it describes was either removed or never ported.

This is why "it renders beautifully" is stronger evidence here than it would
normally be: with no fallback and no status check, there is no degraded path for
the savers to have silently fallen back *to*. It worked or it would have failed
visibly.

It is also why the port must not assume a graceful-degradation path exists to
preserve. There isn't one to preserve.

## Platform state at the baseline

| | value |
| --- | --- |
| deployment target | **26.0**, all three (was 10.9) |
| GL profile | 2.1 compatibility — no `NSOpenGLPFAOpenGLProfile` set anywhere |
| hosting view | `NSOpenGLView`, deprecated since 10.14 |
| signing | ad-hoc, `CODE_SIGN_IDENTITY = "-"`, `CODE_SIGN_STYLE = Manual`, empty team |
| coverage | helios 96.5%, hyperspace 96.5%, hills 94.3% — all at baseline |

hills reaches GL through `Source Code/HillsOpenGLView.h`, `SkyDome.m` and
`HillsScreensaverView.m`, and is the only one of the three with a standalone
`.app` target (`Hills Application`) that can be watched in a window.

## What this baseline does not cover

Stated plainly, because a baseline that overstates itself is worse than none —
it invites a post-port comparison against a "before" nobody actually established.

- **No images.** Nothing here is a screenshot. Every claim about appearance is
  prose, and prose does not survive contact with "is this the same as before?"
- **One observer, one session, one machine.** No second look, no second display,
  no second GPU.
- **No duration.** Whether a saver is stable over minutes, survives sleep/wake,
  or leaks is untested. Screen savers run for hours.
- **Preferences sheets unexercised.** Each saver has a configure sheet — and
  hyperspace's exposes a shader toggle wired to `dShaders`
  (`ConfigureSheet.xib`, tag 7 → `HyperspaceView.mm:302`). Nobody has toggled it,
  which is a missed opportunity: it is a free A/B on whether the shader path is
  what rendered.
- **Multi-display and Retina scaling untested**, though
  `wantsBestResolutionOpenGLSurface = YES` is set.

`ss-pl9`'s own design note is the right calibration for all of this: *manual and
cheap beats automated and unbuilt*, and an offscreen-render plus image-hash
harness is a bigger piece of work that should not gate the port. The gaps above
are recorded so the port knows what it is not protected against, not as a
prerequisite list.
