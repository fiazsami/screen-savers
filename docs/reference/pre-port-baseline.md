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
> **helios and hyperspace render untouched. hills was black and needed four
> fixes to render at all. Options… opens for all three, but only sometimes.**
> Five pre-existing bugs — `ss-hx9`, `ss-2ty`, `ss-0d8`, `ss-8ql` in hills, and
> `ss-kvi` in the host — not one of them caused by a port that has not happened.
> That is the argument for capturing a baseline first, made concrete: four of
> those would have looked exactly like port damage.
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
| helios | **renders** | opens, **intermittently** | works in preview mode |
| hyperspace | **renders** | opens, **intermittently** | works in preview mode |
| hills | **black** as found; **renders** after four fixes | opens, **intermittently** | see below |

**hills now renders**, in preview and full-screen, on the display(s) the
preference selects — confirmed 2026-08-22. It took four separate defects, and
the count is the point: this is what "the pre-port state" actually meant for
hills, and none of it would have been distinguishable from port damage if the
port had gone first.

| | |
| --- | --- |
| `ss-hx9` | `-[NSScreen mainScreen]` is the screen with the *key window*, not the main display. Compared by pointer. **Inverted** the preference — drew on the secondary, refused on the primary. |
| `ss-2ty` | `glView` never followed the host's resize, so full-screen drew a small correct picture in the corner of a black window. Both twins already forward `setFrameSize:`; hills was the only one that did not. |
| `ss-0d8` | `-[NSWindow screen]` is **nil for every window on the secondary display**. The "cannot tell, so draw" fallback fired 25 times in 32, so the preference suppressed nothing. |
| `ss-8ql` | **No hills preference ever persisted** — no plist existed anywhere on the system. Every setting in the sheet reverted on close, so the checkbox could not be changed at all. |

Both columns were first recorded as flat failures. Both turned out to depend on
which display the System Settings window occupies — the preview because of a bug
in hills (`ss-hx9`), the Options… button because of something in the host
(`ss-kvi`). Same axis, unrelated causes.

All three installed to `~/Library/Screen Savers` from a local ad-hoc build and
were selected from System Settings → Screen Saver. Locally built bundles carry
no `com.apple.quarantine` attribute, so no Gatekeeper assessment was involved.
Screenshots are attached to the pull request that added this file.

So the load-and-render claim holds for two of three, and the configure sheet
holds for all three but not reliably. Both are tracked, and **neither is caused
by the port, because the port has not happened** — that is the entire value of
having captured this before opening a Metal branch.

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

**Established, and it was neither of the two explanations first offered here.**
Not a `nil` window, and not a genuine second-display case. `-[NSScreen
mainScreen]` **is not the main display** — it is the screen holding the window
with keyboard focus. Measured on this machine, which has **two** displays, not
the one an earlier draft of this document asserted:

```
window.screen   NSScreenNumber=1   frame={{0,0},{3440,1440}}
mainScreen      NSScreenNumber=2   frame={{0,1440},{3440,1440}}
CGMainDisplayID=1
```

`NSScreen` instances are not pointer-stable either, so `==` was wrong even when
the display was right. The result is not that the preference failed but that it
**inverted**:

| display | shipped code |
| --- | --- |
| 1 — **is** the main display | do **not** draw |
| 2 — not the main display | **draw** |

Hills drew on the secondary display and refused on the primary. That also
explains the intermittency: move System Settings to the primary display and
hills renders, because `mainScreen` follows the focus.

The other two savers decide with `frameRect.origin == (0, 0)` and never call
`mainScreen`, so they are unaffected — checked rather than assumed, since both
ship the same preference.

Fixed in **hills#6**, though not on the first attempt. Comparing `NSScreenNumber`
against `CGMainDisplayID()` asks the right question and is unreachable most of
the time, because `-[NSWindow screen]` is nil for every window on the secondary
display (`ss-0d8`). The signal that works is the window's own frame origin:

```
winOrigin = 0,0        display 1 (main)        16 samples
winOrigin = 0,-1440    display 2 (secondary)   45 samples
```

Note the sign. `NSScreen` places the secondary display at **y = +1440** while the
saver's window for it is at **y = −1440**; the two coordinate spaces disagree,
which is *why* `-[NSWindow screen]` is nil there and why intersecting a window
frame against `NSScreen` frames finds nothing either. The one thing both spaces
agree on is the origin.

### Options… is intermittent, in all three

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
rather than at any one of them.

**Refuted, hours later, and worth reading as a lesson about how.** The suspicion
recorded here was that System Settings does not present configure sheets for
legacy modules. It does. **All three sheets open** once the System Settings
window is on the primary display, and the reporter describes the behaviour as
intermittent — *"when I move the System Settings app the options/preview may or
may not display"*.

So the shared-cause argument reached a true conclusion — the host, not our code —
by a false route. That is the danger of an argument that is only ever checked
against itself: it was labelled a hypothesis and the settling check was named
(*try a saver known to work*), and it still stood here as the leading
explanation until somebody moved a window.

What it actually is: sheet presentation depends on which display System Settings
occupies, intermittently. **Same axis as the hills bug, different cause.** hills
was ours and is fixed; this reproduces for helios and hyperspace, and neither has
any display-conditional logic in its sheet path — both simply `loadNibNamed` and
return the window. Nothing in these three codebases can make a returned
`NSWindow` fail to appear.

Tracked as `ss-kvi`, now narrowed to characterising the intermittency.

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

- **hills' visual baseline is younger than the other two.** Its renderer never
  ran until four host-integration bugs were fixed on 2026-08-22, so what is
  recorded for hills is the behaviour of a *repaired* saver, not the one that
  was inherited. That is the right baseline to port against — `ss-q1r` compares
  against a hills that draws — but it is not the same claim as helios' and
  hyperspace's, which were observed untouched.
- **Nobody has described what any of the three actually looks like.** "Renders
  correctly" is the whole record. No frame, no palette, no motion, nothing a
  post-port reader could compare against beyond "something appeared".
- **Only screenshots of the System Settings pane.** The images on the pull
  request show the preview thumbnails, not a saver running full-screen, and
  nothing has been captured frame by frame. Prose does not survive contact with
  "is this the same as before?"
- **One observer, one session, one machine.** No second look, no second GPU.
  Two displays, both 3440×1440 — an earlier draft of this document said one,
  which is how it mis-ruled-out the explanation that turned out to be right.
- **No duration.** Whether a saver is stable over minutes, survives sleep/wake,
  or leaks is untested. Screen savers run for hours.
- **No settings other than the defaults**, and `ss-kvi` means there is currently
  no way to change them through the UI. hyperspace's shader toggle
  (`ConfigureSheet.xib` tag 7 → `HyperspaceView.mm:302`) would have been a free
  A/B on whether the shader path is what rendered; it is unreachable until
  `ss-kvi` is resolved. `defaults write` on the module domain is the workaround
  and has not been tried.
- **Retina scaling untested**, though `wantsBestResolutionOpenGLSurface = YES`
  is set. Multi-display is no longer wholly untested — `ss-hx9` and `ss-kvi` are
  both findings about it — but nothing has watched a saver run full-screen
  across both displays at once, which is the case the preference exists for.

`ss-pl9`'s own design note is the right calibration for all of this: *manual and
cheap beats automated and unbuilt*, and an offscreen-render plus image-hash
harness is a bigger piece of work that should not gate the port. The gaps above
are recorded so the port knows what it is not protected against, not as a
prerequisite list.
