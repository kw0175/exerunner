#!/usr/bin/env bash
#
# exerunner installer.
#
# On a fresh Linux Mint machine:
#
#   curl -fsSL https://raw.githubusercontent.com/kw0175/exerunner/main/install.sh | bash
#
# Or from a clone:
#
#   ./install.sh
#
# Installs into your home directory. No root needed for exerunner itself -
# only for the system packages it offers to install at the end.
#
set -euo pipefail

REPO="${EXERUNNER_REPO:-kw0175/exerunner}"
BRANCH="${EXERUNNER_BRANCH:-main}"
RAW="https://raw.githubusercontent.com/${REPO}/${BRANCH}"

LIB="${XDG_DATA_HOME:-$HOME/.local/share}/exerunner/bin"
BIN="$HOME/.local/bin"
APPDIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

say()  { printf '\033[36m::\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m ok \033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarn\033[0m %s\n' "$*"; }
die()  { printf '\033[31mSTOP\033[0m %s\n' "$*"; exit 1; }

printf '\n\033[1m  exerunner\033[0m \033[2m run Windows programs on Linux, one clean prefix each\033[0m\n\n'

# --------------------------------------------------------------------------
# prerequisites
# --------------------------------------------------------------------------

command -v python3 >/dev/null || die "python3 is required."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' \
  || die "Python 3.8 or newer is required."

mkdir -p "$LIB" "$BIN" "$APPDIR"

# --------------------------------------------------------------------------
# fetch the program files
# --------------------------------------------------------------------------
# Works both from a git clone and from `curl | bash`, where there is no
# surrounding checkout to copy from.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd || echo '')"
FILES=(exerunner exerunner_gui.py winedoctor)

if [ -n "$HERE" ] && [ -f "$HERE/bin/exerunner" ]; then
  say "Installing from this checkout"
  for f in "${FILES[@]}"; do
    install -m 0644 "$HERE/bin/$f" "$LIB/$f"
  done
else
  say "Downloading from github.com/${REPO}"
  command -v curl >/dev/null || command -v wget >/dev/null \
    || die "Need curl or wget to download."
  for f in "${FILES[@]}"; do
    if command -v curl >/dev/null; then
      curl -fsSL "$RAW/bin/$f" -o "$LIB/$f" || die "Could not download $f"
    else
      wget -qO "$LIB/$f" "$RAW/bin/$f" || die "Could not download $f"
    fi
  done
fi
ok "Program files in $LIB"

# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

cat > "$BIN/exerunner" <<EOF
#!/usr/bin/env bash
exec python3 "$LIB/exerunner" "\$@"
EOF
chmod +x "$BIN/exerunner"

cat > "$BIN/winedoctor" <<EOF
#!/usr/bin/env bash
exec python3 "$LIB/winedoctor" "\$@"
EOF
chmod +x "$BIN/winedoctor"

ok "Commands installed: exerunner, winedoctor"

# --------------------------------------------------------------------------
# desktop integration
# --------------------------------------------------------------------------

cat > "$APPDIR/exerunner.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Windows Apps
Comment=Install and run Windows programs, one clean container per app
Exec=$BIN/exerunner gui
Icon=application-x-executable
Terminal=false
Categories=System;Utility;Wine;
Keywords=wine;windows;exe;
StartupNotify=true
EOF

cat > "$APPDIR/exerunner-open.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Install with exerunner
Comment=Run this Windows program with Wine
Exec=$BIN/exerunner open %f
Icon=application-x-executable
Terminal=false
NoDisplay=true
MimeType=application/x-ms-dos-executable;application/x-msdownload;application/x-msi;application/vnd.microsoft.portable-executable;
EOF

chmod 0644 "$APPDIR"/exerunner*.desktop
update-desktop-database "$APPDIR" 2>/dev/null || true

if command -v xdg-mime >/dev/null; then
  for mime in application/x-ms-dos-executable application/x-msdownload \
              application/x-msi application/vnd.microsoft.portable-executable; do
    xdg-mime default exerunner-open.desktop "$mime" 2>/dev/null || true
  done
fi
ok "Menu entry added, and double-clicking a .exe now opens the installer"

# --------------------------------------------------------------------------
# PATH
# --------------------------------------------------------------------------

case ":$PATH:" in
  *":$BIN:"*) ;;
  *)
    if [ -f "$HOME/.bashrc" ] && ! grep -qs 'HOME/.local/bin' "$HOME/.bashrc"; then
      printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME/.bashrc"
      ok "Added ~/.local/bin to your PATH"
    fi
    export PATH="$BIN:$PATH"
    warn "Open a new terminal for the commands to be found."
    ;;
esac

# --------------------------------------------------------------------------
# system packages
# --------------------------------------------------------------------------

MISSING=()
command -v wine       >/dev/null || MISSING+=(wine)
command -v winetricks >/dev/null || MISSING+=(winetricks)
command -v wrestool   >/dev/null || MISSING+=(icoutils)
command -v cabextract >/dev/null || MISSING+=(cabextract)
python3 -c 'import gi' 2>/dev/null || MISSING+=(python3-gi gir1.2-gtk-3.0)

echo
if [ ${#MISSING[@]} -eq 0 ]; then
  ok "Everything exerunner needs is already installed."
else
  warn "These are missing: ${MISSING[*]}"
  if command -v apt >/dev/null && [ -t 0 ]; then
    read -r -p "       Install them now with apt? [Y/n] " reply
    if [[ ! "$reply" =~ ^[Nn] ]]; then
      sudo apt update && sudo apt install -y "${MISSING[@]}"
      ok "System packages installed"
    fi
  else
    echo "       sudo apt install ${MISSING[*]}"
  fi
fi

cat <<EOF

$(printf '\033[32m ok \033[0m') Installed.

  Check your system is ready:
      exerunner doctor

  Install a Windows program:
      exerunner install ~/Downloads/setup.exe
      ... or just double-click any .exe in your file manager

  Graphical version:
      exerunner gui           (also in the menu as 'Windows Apps')

  When something fails, find out why:
      exerunner logs <app> -e
      winedoctor --app <app> --fix

EOF
