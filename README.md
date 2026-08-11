# exerunner

Run Windows programs on Linux without the usual Wine misery.

```bash
curl -fsSL https://raw.githubusercontent.com/OWNER/exerunner/main/install.sh | bash
exerunner doctor
```

Then double-click any `.exe` in your file manager.

---

## What this is

Wine is the only thing on Linux that runs Windows binaries. Bottles, Lutris,
PlayOnLinux, CrossOver and Steam's Proton are all wrappers around it. So is
this. The value isn't in replacing Wine — it's in using Wine the way that
actually works, every time, without you having to know how.

Almost every "I tried Wine and it was a nightmare" story is one of five things:

| The problem | What exerunner does |
|---|---|
| Everything installs into one shared `~/.wine`, so apps overwrite each other's runtimes | Every app gets its own isolated prefix |
| Apps need Visual C++ / .NET / Microsoft fonts, which Wine can't legally ship | Installs the right runtime bundle per app |
| The distro's Wine is years old and fails on things current Wine handles | `doctor` detects it and gives you the exact commands for your release |
| 32-bit support isn't enabled, producing cryptic loader errors | `doctor` catches it |
| Something fails and the log is 4,000 lines of noise | `winedoctor` translates it into English |

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/OWNER/exerunner/main/install.sh | bash
```

Installs to `~/.local` only. It'll offer to `apt install` anything missing —
Wine, winetricks, icoutils — and you can decline.

From a clone instead:

```bash
git clone https://github.com/OWNER/exerunner.git
cd exerunner && ./install.sh
```

## Use

**Graphically:** double-click a `.exe`, or open **Windows Apps** from the menu.

**From a terminal:**

```bash
exerunner doctor                      # is this machine ready?
exerunner install ~/Downloads/setup.exe
exerunner list
exerunner run <app>
exerunner logs <app> -e               # error lines only
exerunner deps <app> --preset directx # add runtimes afterwards
exerunner desktop <app>               # put an icon on the desktop
exerunner shell <app> --winecfg       # Wine settings for this app alone
exerunner rm <app>
```

### Install options

| Flag | Use |
|---|---|
| `--preset <name>` | Runtime bundle, see below |
| `--arch 32` | Old 32-bit programs |
| `--winver winxp\|win7\|win10` | What Windows version to claim |
| `--portable` | Not an installer — runs directly |
| `--in-place` | Portable, run where it already lives (best for large games) |
| `--with-folder` | Portable, copy the whole containing folder |
| `--runner <name>` | Use an alternative Wine build |

### Runtime presets

| Preset | Contents |
|---|---|
| `app` (default) | corefonts, vcrun2022, msxml6, gdiplus |
| `dotnet` | plus .NET Framework 4.8 |
| `directx` | d3dx9/10/11, d3dcompiler, xact |
| `game` | the above plus DXVK |
| `media` | quartz, devenum for DirectShow |
| `full` | everything, for troubleshooting |
| `minimal` | nothing |

## winedoctor

Wine's failures are highly patterned. This maps them to plain English and,
where possible, a command that fixes it.

```bash
winedoctor --app notepad              # read that app's last log
winedoctor wine.log --fix             # explain, then install what's missing
wine app.exe 2>&1 | winedoctor -      # straight from a pipe
```

It reports severity — blocking, likely, informational — and collapses the
hundreds of `fixme:` lines into one entry explaining they're normal.

Crucially, anything it *doesn't* recognise is reported as **UNKNOWN** with a
warning not to read the summary as a clean run. A diagnostic tool that stays
silent about what it doesn't understand is worse than no tool, because silence
reads as an all-clear.

## About DirectX

**Never run Microsoft's redistributable installers under Wine.** `dxwebsetup.exe`,
`vc_redist.exe` and the .NET web installers all fetch their payload through
Windows Update, which doesn't exist here. exerunner detects these by filename
and warns you.

**Wine already implements DirectX.** There's nothing to install. What games
need are the redistributable helper DLLs — `d3dx9_43.dll`, `d3dcompiler_47.dll`,
`xactengine` — which is what `--preset directx` provides.

The working method: install lean, run it, and only fix what actually breaks. A
prefix containing just what it needs is more reliable than one stuffed with
everything.

## Alternative Wine builds

Some programs only work on a patched Wine. Install one per app without touching
your system Wine:

```bash
exerunner runners search kron4ek
exerunner runners add wine-9 <url>
exerunner install setup.exe --runner wine-9
```

## Requirements

- Linux with Wine (Mint, Ubuntu, Debian and relatives are what it's tested on)
- Python 3.8+
- `winetricks` for runtime bundles, `icoutils` for icon extraction
- `python3-gi` and `gir1.2-gtk-3.0` for the graphical parts

`exerunner doctor` checks all of this and tells you what to install.

## Where things live

```
~/.local/share/exerunner/apps/<app>/prefix/   the app's isolated C: drive
~/.local/share/exerunner/apps/<app>/logs/     install.log and last.log
~/.local/share/exerunner/runners/             extra Wine builds
~/.local/share/applications/                  menu entries
```

Prefixes are self-contained directories. Back one up by copying it; remove an
app and its prefix goes with it.

## Honest limitations

- **This doesn't make Wine more compatible.** If a program genuinely won't run
  under Wine, no wrapper fixes that. Check
  [appdb.winehq.org](https://appdb.winehq.org) first.
- **Kernel anti-cheat games will never work.** That isn't a bug — detecting and
  refusing non-Windows environments is the product working as intended.
- **Adobe CC and current Microsoft Office don't work properly.**
- **For games, use Steam with Proton.** Valve ships a Wine fork with DXVK and
  per-game configuration already applied, verified on
  [protondb.com](https://protondb.com). exerunner fills the other gap: business
  software, utilities and one-off tools nobody has published a config for.
- **Main-executable detection is a heuristic.** It reads the Start Menu
  shortcuts an installer creates and ranks new `.exe` files. When unsure it
  asks, and you can correct `manifest.json` by hand.

## Licence

MIT.
