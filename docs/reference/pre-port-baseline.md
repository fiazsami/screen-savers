# The pre-port baseline

What the three savers do on macOS 26, recorded **before** any Metal branch opens.

This exists because of `ss-pl9`, and because of one asymmetry: once a port lands
you can never go back and capture the "before" picture. If a ported saver renders
black, an uncaptured baseline cannot tell you whether the port broke it or whether
it was already broken.

The *why* behind the port sequencing lives in [`doctrine.md`](doctrine.md); the
harness that measures the code lives in [`tooling.md`](tooling.md).

> **Status.** Observed from System Settings on macOS 26 on 2026-08-22 — the
> first time anything in this project has verified a pixel. Everything the 398
> characterization cases prove is about where a vertex *is*; none of it is about
> whether anything appears on screen.
>
> **helios and hyperspace render. hills does not — it is black. The Options…
> button does nothing in any of the three.** Two pre-existing bugs, `ss-hx9` and
> `ss-kvi`, neither of them caused by a port that has not happened.
>
> The record below is in two halves with different standing. The **code-path**
> half is read out of the source and is as reliable as reading. The
> **observational** half is one person, one machine, one session — see *What
> this baseline does not cover*.
>
> **This document's first draft said all three worked**, on the strength of a
> summary judgement, and the first review refuted it with screenshots. Recorded
> rather than quietly edited, because the failure is instructive: the
> overstatement was in the headline, not in the gaps list, so the section
> written to prevent exactly this did not catch it. A baseline claiming "all
> three work" when one does not is worse than no baseline — it would have let
> the port take credit for a fix it did not make, or blame for a break it did
> not cause.

## What was observed

| saver | preview | Options… | notes |
| --- | --- | --- | --- |
| helios | **renders** | **does nothing** | works in preview mode |
| hyperspace | **renders** | **does nothing** | works in preview mode |
| hills | **black — nothing renders** | **does nothing** | see below |

All three installed to `~/Library/Screen Savers` from a local ad-hoc build and
were selected from System Settings → Screen Saver. Locally built bundles carry
no `com.apple.quarantine` attribute, so no Gatekeeper assessment was involved.
Screenshots are attached to the pull request that added this file.

So the load-and-render claim holds for two of three, and the configure sheet
holds for none. Both are tracked, and **neither is caused by the port, because
the port has not happened** — that is the entire value of having captured this
before opening a Metal branch.

### hills renders nothing — `HillsScreensaverView.m:87`

```objc
- (void)startAnimation
{
    if ( mMainDisplayOnly &&
        ([[self window] screen] != [NSScreen mainScreen]) )
    {
        [glView setRender:false];
    }
    else
    {
        [glView setRender:true];
        [super startAnimation];
    }
}
```

`mMainDisplayOnly` defaults to **true** (`MAIN_DISPLAY_KEY`, registered at
`HillsScreensaverView.m:45`, read at `:238`). `HillsOpenGLView` also starts with
`mRender = false` under `#ifdef SCREENSAVER` (`HillsOpenGLView.m:39–44`), and its
`drawRect:` is wrapped in `if(mRender)` (`:84`) — so *false is the initial state
and this method is the only thing that clears it*.

When the condition is met the view draws nothing **and** `[super startAnimation]`
is never reached, so the animation timer never starts either. That matches the
observation exactly: a permanently black preview rather than a stalled frame.

The modern host runs the saver out of process in `legacyScreenSaver.appex`, so
`[self window]` is not the window this check was written against in 2006. Two
paths reach the same result and it is **not yet established which one fires**:
`[self window]` being `nil` at `startAnimation` time — `[nil screen]` is `nil`,
and `nil != [NSScreen mainScreen]` is true — or a real window whose screen is not
`mainScreen`. Both were single-display cases on a 3440×1440 display, so a
multi-monitor explanation is ruled out.

The other two savers have no main-display gate, which is why they are unaffected.
Tracked as `ss-hx9`.

### Options… does nothing, in all three

Not a missing resource. Every bundle ships its nib:

```
Helios.saver/Contents/Resources/Base.lproj/Helios.nib
Hyperspace.saver/Contents/Resources/Base.lproj/ConfigureSheet.nib
Hills.saver/Contents/Resources/Base.lproj/ConfigureSheet.nib
```

and all three implement `-hasConfigureSheet` and `-configureSheet`
(`HeliosView.mm:251`, `HyperspaceView.mm:213`, `HillsScreensaverView.m:135`).

The savers are three independent implementations — two authors, different nib
names, different outlet wiring — failing identically. That points at the host
rather than at any one of them, and the current suspicion is that System
Settings does not present legacy configure sheets. **This is a hypothesis, not
a measurement**: it has not been tested against a saver known to work, which is
the check that would settle it. Tracked as `ss-kvi`.

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

This makes the two savers that *do* render stronger evidence than they would
normally be. With no fallback and no status check there is no degraded path they
could have silently fallen back *to*, so helios and hyperspace rendering means
the real VBO and shader paths ran.

It cuts the other way for hills, and is worth stating so nobody reads `ss-hx9`
as a rendering failure: hills is black because `startAnimation` explicitly turns
drawing off, not because anything in GL failed. Its renderer has not been
exercised at all, in either direction. **hills therefore has no visual baseline**,
and `ss-q1r` — the port that unblocks its coverage — is the one port with nothing
to compare against.

Above all, the port must not assume a graceful-degradation path exists to
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

- **hills has no visual baseline at all.** `ss-hx9` means its renderer never
  ran. Nothing here describes what hills is supposed to look like, so `ss-q1r`
  has no "before" to port against. Fixing `ss-hx9` first is what would create
  one.
- **Only screenshots of the System Settings pane.** The images on the pull
  request show the preview thumbnails, not a saver running full-screen, and
  nothing has been captured frame by frame. Prose does not survive contact with
  "is this the same as before?"
- **One observer, one session, one machine.** No second look, no second display,
  no second GPU. The single display was 3440×1440.
- **No duration.** Whether a saver is stable over minutes, survives sleep/wake,
  or leaks is untested. Screen savers run for hours.
- **No settings other than the defaults**, and `ss-kvi` means there is currently
  no way to change them through the UI. hyperspace's shader toggle
  (`ConfigureSheet.xib` tag 7 → `HyperspaceView.mm:302`) would have been a free
  A/B on whether the shader path is what rendered; it is unreachable until
  `ss-kvi` is resolved. `defaults write` on the module domain is the workaround
  and has not been tried.
- **Multi-display and Retina scaling untested**, though
  `wantsBestResolutionOpenGLSurface = YES` is set — and note `ss-hx9` is
  specifically a multi-display-aware code path misfiring on a single display,
  so this gap is larger than it looks.

`ss-pl9`'s own design note is the right calibration for all of this: *manual and
cheap beats automated and unbuilt*, and an offscreen-render plus image-hash
harness is a bigger piece of work that should not gate the port. The gaps above
are recorded so the port knows what it is not protected against, not as a
prerequisite list.
